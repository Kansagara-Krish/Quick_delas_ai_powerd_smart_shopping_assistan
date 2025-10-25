from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import joblib
import json
import os
import numpy as np
from difflib import get_close_matches

app = FastAPI()

# --- Setup Directories ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DATA_FILE = os.path.join(BASE_DIR, "data", "products.json")
MODEL_FILE = os.path.join(BASE_DIR, "xgb_ranking_pipeline.joblib")

# Mount static files (e.g., css, js)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    print(f"⚠️ Warning: 'static' directory not found at {STATIC_DIR}")

# Mount templates (e.g., index.html)
if os.path.exists(TEMPLATES_DIR):
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
else:
    print(f"❌ ERROR: 'templates' directory not found at {TEMPLATES_DIR}. UI will not load.")
    templates = None # App will fail, which is expected


# --- Load Dataset ---
def load_dataset():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # We need the 'products' list, not the root object
        products_list = data.get("products", []) 
        print(f"✅ Loaded {len(products_list)} products from {DATA_FILE}.")
        return products_list
    except Exception as e:
        print(f"❌ Error loading JSON dataset from {DATA_FILE}: {e}")
        return []

products_data = load_dataset()


# --- Load ML Model ---
try:
    obj = joblib.load(MODEL_FILE)
    preproc = obj["preproc"]
    model = obj["model"]
    print(f"✅ ML model loaded successfully from {MODEL_FILE}!")
except Exception as e:
    print(f"⚠️ Warning: ML model not loaded. Using fallback ranking. Error: {e}")
    preproc = None
    model = None


# --- Inference Function ---
def infer_topk(df, k=3):
    if preproc is None or model is None:
        print("Using fallback ranking (model not loaded).")
        # Simple scoring formula (if no model available)
        # Ensure columns exist before using them
        df['price'] = pd.to_numeric(df.get('price', 1)).fillna(1)
        df['rating'] = pd.to_numeric(df.get('rating', 0)).fillna(0)
        df['delivery_in_days'] = pd.to_numeric(df.get('delivery_in_days', 3)).fillna(3)
        
        df["_pred_score"] = (
            0.4 * (1 - (df["price"] / (df["price"].max() + 1e-6))) +
            0.3 * (df["rating"] / 5) +
            0.3 * (1 - df["delivery_in_days"] / (df["delivery_in_days"].max() + 1e-6))
        )
    else:
        print("Using XGBoost model for ranking.")
        # Ensure all feature columns for the model exist, filling missing
        feature_names = preproc.feature_names_in_
        for col in feature_names:
            if col not in df.columns:
                df[col] = np.nan # Add missing cols as NaN, imputer will handle
                
        # Re-order columns to match preprocessor expectation
        df_for_model = df[feature_names]
        
        X_proc = preproc.transform(df_for_model)
        preds = model.predict(X_proc)
        df["_pred_score"] = preds

    return df.sort_values("_pred_score", ascending=False).head(k)


# --- Utility to find product by name ---
def find_product_by_name(query):
    all_names = [p["product_name"] for p in products_data]
    if not all_names:
        return None
    matches = get_close_matches(query, all_names, n=1, cutoff=0.4)
    if not matches:
        return None
    return next((p for p in products_data if p["product_name"] == matches[0]), None)


# --- API Routes ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<h1>Error: 'templates' directory not found.</h1>", status_code=500)

@app.get("/compare.html", response_class=HTMLResponse)
def compare_page(request: Request):
    if templates:
        return templates.TemplateResponse("compare.html", {"request": request})
    return HTMLResponse("<h1>Error: 'templates' directory not found.</h1>", status_code=500)

@app.get("/index.html", response_class=HTMLResponse)
def index_page(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<h1>Error: 'templates' directory not found.</h1>", status_code=500)

@app.post("/chat", response_class=JSONResponse)
async def chat(request: Request):
    data = await request.json()
    user_input = data.get("message", "").strip()

    if not user_input:
        return JSONResponse({"bot": "Please type a product name to search 🔍", "products": []})

    # Find the closest product by name
    product = find_product_by_name(user_input)
    if not product:
        return JSONResponse({"bot": f"❌ Sorry, I couldn't find '{user_input}' in our catalog.", "products": []})

    # --- CRITICAL CHANGE HERE ---
    # Flatten offers into a DataFrame WITH ALL MODEL FEATURES
    offers = []
    for variant in product.get("variants", []):
        specs = variant.get("specifications", {})
        for offer in variant.get("offers", []):
            offers.append({
                # --- Features for Model ---
                "brand": product.get("brand"),
                "price": offer.get("price"),
                "rating": offer.get("rating"),
                "rating_count": offer.get("rating_count"),
                "delivery_in_days": offer.get("delivery_in_days"),
                "is_trusted_seller": offer.get("is_trusted_seller"),
                "RAM_GB": specs.get("RAM_GB"),
                "warranty_months": specs.get("warranty_months"),
                "is_replaceable": specs.get("is_replaceable"),
                "Color": specs.get("Color"),

                # --- Features for UI Display ---
                "product_name": product["product_name"],
                "seller_name": offer.get("seller_name"),
                # Pass the full specs dict to the UI
                "specifications": { 
                    "RAM": f"{specs.get('RAM_GB', 'N/A')} GB",
                    "Storage": f"{specs.get('Storage_GB', 'N/A')} GB",
                    "Color": specs.get('Color', 'N/A'),
                    "Warranty": f"{specs.get('warranty_months', 'N/A')} Months",
                    "Replaceable": "Yes" if specs.get('is_replaceable') else "No"
                }
            })

    if not offers:
        return JSONResponse({"bot": f"No offers found for {product['product_name']} 😞", "products": []})

    df = pd.DataFrame(offers)
    
    # Run inference
    topk = infer_topk(df, k=3)
    results = topk.to_dict(orient="records")

    # Format for frontend display
    formatted_results = []
    for p in results:
        formatted_results.append({
            "name": p["product_name"],
            "platform": p.get("seller_name", "Unknown Seller"),
            "price": f"₹{int(p['price']):,}" if p.get('price') else "N/A",
            "rating": round(p["rating"], 1) if p.get('rating') else "N/A",
            "score": round(p["_pred_score"], 3),
            "is_trusted": p.get("is_trusted_seller", False),
            "specs": p.get("specifications", {}) # Send the whole specs object
        })

    # Response
    return JSONResponse({
        "bot": f"📦 Here are the top 3 deals I found for **{product['product_name']}**:",
        "products": formatted_results, # Send formatted results
        "image": product.get("base_image_url", ""),
        "description": product.get("description", "")
    })


if __name__ == "__main__":
    import uvicorn
    # This will run the app on http://127.0.0.1:8000
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)