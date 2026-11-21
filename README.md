# 🛒 AI Shopping Agent

An AI-powered shopping assistant built with **LangChain, Groq LLM, Python, Streamlit, and SQLite**. It helps users discover products, compare options, manage shopping carts, place orders, and interact with an AI agent through natural language.

The application uses an LLM-powered agent with tools to perform shopping operations and maintain persistent conversation history.

## ✨ Features

### 1. AI-Powered Product Search
- Search products using natural language.
- Filter products based on category, price, rating, and other criteria.
- Retrieve relevant product information from the database.

### 2. Product Comparison
- Compare multiple products.
- Evaluate price and customer ratings.
- Help users make informed purchasing decisions.

### 3. Shopping Cart Management
- Add products to the shopping cart.
- View cart items and quantities.
- Update product quantities.
- Remove products from the cart.

### 4. Order Management
- Create orders from shopping cart items.
- Confirm pending orders.
- View order history.
- Cancel eligible orders.
- Track order status.

### 5. Persistent Conversation Memory
- Automatically save conversations.
- Access previous conversations.
- Continue earlier conversations.
- Create new conversations.
- Delete conversation history.

### 6. Conversational AI Interface
- Interact with the shopping assistant using natural language.
- Execute shopping operations through AI-powered tools.
- Get contextual responses from the agent.

## 🧰 Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| LangChain | AI agent orchestration |
| Groq | LLM inference |
| GPT-OSS-120B | Language model |
| Streamlit | User interface |
| SQLite | Database and persistent storage |
| SQL | Data querying and management |
| Python-dotenv | Environment variable management |

## 🏗️ Architecture

The application follows a tool-based AI agent architecture.

```text
                 User
                   |
                   v
             Streamlit UI
                   |
                   v
             AI Shopping Agent
                   |
              LangChain
                   |
                   v
              Groq LLM
                   |
                   v
             Agent Tools
                   |
       +-----------+-----------+
       |           |           |
       v           v           v
   Product      Shopping     Order
    Search        Cart      Management
       |           |           |
       +-----------+-----------+
                   |
                   v
                SQLite
                   |
                   v
          Persistent Storage

       Conversation Memory
             SQLite
```

## 🚀 Getting Started

### Prerequisites

- Python installed
- Git installed
- Groq API key

### 1. Clone the Repository

```bash
git clone https://github.com/ShrikantKumar123/AI-Shopping-Agent.git

cd AI-Shopping-Agent
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the environment:

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows**

```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
```

Replace `your_groq_api_key` with your actual Groq API key.

### 5. Run the Application

```bash
streamlit run app.py
```

The application will open in your browser.

## 💬 Example Queries

Try these queries with the AI Shopping Agent:

- Find organic honey under $20 with a 4.5+ rating.
- Show me the best-rated coffee.
- Compare products 1, 2, and 3.
- Add product 1 to my cart.
- Show my shopping cart.
- Update the quantity of product 1.
- Create an order from my cart.
- Show my order history.
- Cancel my pending order.

## 🗄️ Database

The application uses SQLite for local data persistence.

The database stores information related to:

- Products
- Product reviews
- Shopping orders
- Shopping cart data
- User conversations
- Conversation messages

## 🔐 Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | API key used to access Groq LLM services |

**Important:** Never commit your `.env` file or expose your API key on GitHub.

## 🔮 Future Enhancements

- User authentication and authorization.
- Personalized product recommendations.
- Product review sentiment analysis.
- Multi-agent architecture.
- Agent evaluation and performance monitoring.
- Human approval for sensitive shopping operations.

## 👨‍💻 Author

**Shrikant Kumar**

GitHub: [ShrikantKumar123](https://github.com/ShrikantKumar123)

---

⭐ If you find this project interesting, consider giving it a star!