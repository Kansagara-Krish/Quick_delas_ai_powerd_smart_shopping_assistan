// Default product comparison data
const defaultProducts = {
  phone: {
    name: "iPhone 14",
    price: 999,
    platform: "Apple",
    specs: ["A15 Bionic", "6.1\" OLED", "12MP Dual Camera"],
    rating: 4.8,
    spec_score: 95,
    suggestions: [
      "iPhone 13", "Samsung Galaxy S23", "Google Pixel 7"
    ]
  },
  laptop: {
    name: "MacBook Pro M2",
    price: 1299,
    platform: "Apple",
    specs: ["M2 chip", "13.3\" Retina", "8GB RAM"],
    rating: 4.9,
    spec_score: 98,
    suggestions: [
      "Dell XPS 13", "Lenovo ThinkPad X1", "ASUS ROG"
    ]
  },
  headphones: {
    name: "AirPods Pro",
    price: 249,
    platform: "Apple",
    specs: ["Active Noise Cancellation", "Spatial Audio", "Water Resistant"],
    rating: 4.7,
    spec_score: 92,
    suggestions: [
      "Sony WH-1000XM4", "Bose QuietComfort", "Samsung Galaxy Buds"
    ]
  }
};

// Update chatForm event listener
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;
  
  // Check for product category
  const msgLower = message.toLowerCase();
  let defaultComparison = null;
  if (msgLower.includes('phone')) defaultComparison = defaultProducts.phone;
  if (msgLower.includes('laptop')) defaultComparison = defaultProducts.laptop;
  if (msgLower.includes('headphone')) defaultComparison = defaultProducts.headphones;
  
  // Add user message
  addMessage('user', message);
  userInput.value = "";
  
  // Add loading state
  chatForm.classList.add('loading');
  sendButton.classList.add('loading');
  sendButton.disabled = true;

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: message})
    });
    
    const data = await response.json();
    
    // Add bot response
    addMessage('bot', data.bot);

    // If we have a default comparison, show it first
    if (defaultComparison) {
      const comparisonDiv = document.createElement("div");
      comparisonDiv.className = "bot-message comparison-card";
      comparisonDiv.innerHTML = `
        <strong>Comparing with ${defaultComparison.name} 📱</strong>
        <div class="comparison-specs">
          <div class="spec-item highlight">
            <span class="spec-label">Price:</span>
            <span class="spec-value price-inr">${formatINR(defaultComparison.price * 87)}</span>
          </div>
          ${defaultComparison.specs.map(spec => `
            <div class="spec-item">
              <span class="spec-label">•</span>
              <span class="spec-value">${spec}</span>
            </div>
          `).join('')}
          <div class="spec-item">
            <span class="spec-label">Rating:</span>
            <span class="spec-value">⭐ ${defaultComparison.rating}/5</span>
          </div>
        </div>
        <div class="suggestion-section">
          <div class="suggestion-title">🔍 Similar Products to Consider:</div>
          <div class="suggestion-list">
            ${defaultComparison.suggestions.map(sugg => `
              <div class="suggestion-item">• ${sugg}</div>
            `).join('')}
          </div>
        </div>
      `;
      chatBox.appendChild(comparisonDiv);
    }

    // Display products if available
    if (data.products && data.products.length > 0) {
      const prodContainer = document.createElement("div");
      prodContainer.className = "products-container";
      
      data.products.forEach(p => {
        const inrPrice = convertToINR(p.price) * 87;
        const card = document.createElement("div");
        card.className = "product-card";
        
        // Compare with default product if available
        let priceComparison = '';
        if (defaultComparison) {
          const defaultPrice = defaultComparison.price * 87;
          const priceDiff = inrPrice - defaultPrice;
          const priceDiffText = priceDiff > 0 ? 
            `<span class="price-diff higher">₹${formatINR(Math.abs(priceDiff))} more</span>` :
            `<span class="price-diff lower">₹${formatINR(Math.abs(priceDiff))} less</span>`;
          priceComparison = `
            <div class="price-comparison">
              ${priceDiffText} than ${defaultComparison.name}
            </div>
          `;
        }
        
        card.innerHTML = `
          <strong>${p.product_name}</strong>
          <div class="product-feature">
            <span class="feature-name">Platform:</span>
            <span class="feature-value">${p.platform}</span>
          </div>
          <div class="product-feature">
            <span class="feature-name">Price:</span>
            <span class="feature-value price-inr">${formatINR(inrPrice)}</span>
            ${priceComparison}
          </div>
          <div class="product-feature">
            <span class="feature-name">Rating:</span>
            <span class="feature-value">${p.seller_rating}/5</span>
          </div>
          <div class="product-feature">
            <span class="feature-name">Spec Score:</span>
            <span class="feature-value">${p.spec_score}%</span>
          </div>
          <div class="product-score">
            Match Score: ${p._pred_score}
          </div>
          <button 
            onclick="addToCart({...${JSON.stringify(p)}, inrPrice: ${inrPrice}})" 
            class="add-to-cart-btn"
            id="cart-btn-${p.product_name.replace(/[^a-zA-Z0-9]/g, '-')}"
            ${isProductInCart(p.product_name) ? 'disabled' : ''}>
            ${isProductInCart(p.product_name) ? '✓ Added to Cart' : '🛒 Add to Cart'}
          </button>
        `;
        prodContainer.appendChild(card);
      });
      
      chatBox.appendChild(prodContainer);
    }
    
  } catch (error) {
    console.error('Error:', error);
    addMessage('bot', "Sorry, I'm having trouble connecting to the server. Please try again.");
  } finally {
    // Remove loading state
    chatForm.classList.remove('loading');
    sendButton.classList.remove('loading');
    sendButton.disabled = false;
    
    // Add success animation
    sendButton.classList.add('success');
    setTimeout(() => {
      sendButton.classList.remove('success');
    }, 1000);
    
    chatBox.scrollTop = chatBox.scrollHeight;
  }
});