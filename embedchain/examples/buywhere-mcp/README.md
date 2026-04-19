# EmbedChain - BuyWhere Shopping Agent

Build a shopping agent powered by EmbedChain and BuyWhere's product catalog API. This template enables RAG-based shopping assistance with real-time price comparison and product search.

## Live Demo

[BuyWhere AI Shopping Assistant](https://buywhere.ai) - Experience the power of AI-powered shopping search.

## Features

- **Product Search**: Search across 1.5M+ products from Singapore and global e-commerce platforms
- **Price Comparison**: Find the best deals across Shopee, Lazada, Carousell, Qoo10, and more
- **Deal Discovery**: Find products with significant discounts
- **Category Browsing**: Explore products by category

## How It Works

This template combines:
1. **EmbedChain** - RAG framework for building personalized AI agents
2. **BuyWhere MCP** - Model Context Protocol server for product search and price comparison

## Setup Instructions

1. **Fork this template**

   Navigate to [mem0ai/mem0](https://github.com/mem0ai/mem0) and fork the repository, then:
   ```bash
   cd <your_fork>/embedchain/examples/buywhere-mcp
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file with your API keys:
   ```
   BUYWHERE_API_KEY=your_buywhere_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

   Get your BuyWhere API key at [buywhere.ai/developers](https://buywhere.ai/developers)

4. **Run the app**

   ```bash
   ec dev
   ```

   Or run directly with Streamlit:
   ```bash
   streamlit run app.py
   ```

## Usage

The shopping agent can help you:

- Find specific products across multiple platforms
- Compare prices for the same product
- Discover deals and discounts
- Get product recommendations

## API Reference

### BuyWhere MCP Tools

| Tool | Description |
|------|-------------|
| `search_products` | Search products by keyword with filters |
| `get_product` | Get full product details by ID |
| `find_best_price` | Find cheapest listing for a product |
| `get_deals` | Discover discounted products |

## Deploy

Deploy directly to Streamlit Cloud:

[![Deploy to Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_github.svg)](https://streamlit.io/cloud)

## Resources

- [BuyWhere API Documentation](https://docs.buywhere.ai)
- [EmbedChain Documentation](https://docs.embedchain.ai)
- [MCP Protocol Documentation](https://modelcontextprotocol.io)

## License

Apache 2.0