import pandas as pd
import json
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error  
import joblib
import os
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

def load_and_flatten_data(json_path):
    """
    Loads the nested JSON and flattens it into a DataFrame where each row 
    is a unique offer for a product variant.
    """
    print(f"Attempting to load data from: {json_path}")
    if not os.path.exists(json_path):
        print(f"❌ ERROR: File not found at {json_path}")
        print("Please make sure your updated 'products.json' is in a 'data' folder.")
        return None
        
    with open(json_path, 'r', encoding="utf-8") as f:
        data = json.load(f)
    
    rows = []
    for product in data['products']:
        for variant in product['variants']:
            specs = variant.get('specifications', {})
            for offer in variant['offers']:
                row = {
                    'product_name': product['product_name'],
                    'brand': product.get('brand'),
                    'variant_id': variant['variant_id'],
                    'price': offer.get('price'),
                    'rating': offer.get('rating'),
                    'rating_count': offer.get('rating_count'),
                    'delivery_in_days': offer.get('delivery_in_days'),
                    'is_trusted_seller': offer.get('is_trusted_seller'),
                    'RAM_GB': specs.get('RAM_GB'),
                    'Storage_GB': specs.get('Storage_GB'),
                    'Color': specs.get('Color'),
                    'warranty_months': specs.get('warranty_months'),
                    'is_replaceable': specs.get('is_replaceable')
                }
                rows.append(row)
    
    df = pd.DataFrame(rows)
    print(f"✅ Loaded and flattened {len(df)} offers.")
    return df

def main():
    # 1. Load and prepare data
    # Assumes your JSON is in a folder named 'data' as per your app.py
    df = load_and_flatten_data('data/products.json')
    if df is None:
        return

    # 2. Feature Engineering: Define "bestness_score"
    # This will be our target 'y' for the model
    
    # Convert types and fill NaNs for calculation
    df['price'] = pd.to_numeric(df['price']).fillna(1) # Avoid divide by zero
    df['rating'] = pd.to_numeric(df['rating']).fillna(0)
    df['rating_count'] = pd.to_numeric(df['rating_count']).fillna(0)

    # Score = (Rating * log(Rating Count + 1)) / (Price / 1000)
    # This rewards high, popular ratings and penalizes high prices.
    df['bestness_score'] = (df['rating'] * np.log1p(df['rating_count'])) / (df['price'] / 1000)
    
    # 3. Define features (X) and target (y)
    
    # We use all the features from your JSON that are useful for ranking
    numeric_features = [
        'price', 'rating', 'rating_count', 'delivery_in_days', 
        'RAM_GB', 'warranty_months'
    ]
    categorical_features = ['brand', 'Color']
    boolean_features = ['is_trusted_seller', 'is_replaceable']
    
    features = numeric_features + categorical_features + boolean_features
    
    X = df[features]
    y = df['bestness_score']

    # 4. Preprocessing Pipeline
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')), # Fill missing RAM, warranty, etc.
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])
    
    # Use 'passthrough' for boolean features as they are already 0/1 (or T/F)
    # Convert bools to int just in case
    X.loc[:, boolean_features] = X[boolean_features].fillna(False).astype(int)
    preproc = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features),
            ('bool', 'passthrough', boolean_features)
        ],
        remainder='drop' # Drop any columns not specified
    )

    # 5. Fit the preprocessor
    print("Fitting preprocessor...")
    X_proc = preproc.fit_transform(X)
    
    # 6. Train XGBoost Model
    print("Training XGBoost model...")
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=RANDOM_SEED,
        objective="reg:squarederror"
    )

    model.fit(X_proc, y)

    # 7. Evaluate (optional)
    pred = model.predict(X_proc)
    rmse = np.sqrt(mean_squared_error(y, pred))
    print(f"Model training complete. RMSE on training set: {rmse:.4f}")

    # 8. Save pipeline + model
    joblib.dump({"preproc": preproc, "model": model}, "xgb_ranking_pipeline.joblib")
    print("✅ Pipeline saved to xgb_ranking_pipeline.joblib")

if __name__ == "__main__":
    main()