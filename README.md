# 🛒 AI Shopping Agent

An AI-powered shopping assistant built using **Python, LangChain, Groq, Streamlit, and SQLite**. It allows users to search grocery products, compare products, manage shopping carts, place orders, and interact with an AI shopping assistant using natural language.

The application uses a tool-calling LangChain agent powered by Groq's `openai/gpt-oss-120b` model. It also supports user authentication and persistent, user-specific shopping and conversation data.

## ✨ Features

### 1. AI-Powered Product Search
- Search grocery products using natural language.
- Filter products by keyword, category, price range, and organic status.
- Filter products using minimum customer ratings.
- Display product details, average ratings, and review counts.

### 2. Product Comparison
- Compare two to five products at a time.
- Compare product prices, ratings, and review counts.
- Identify the cheapest and highest-rated products.
- Get AI-assisted product comparison results.

### 3. Shopping Cart
- Add products to the shopping cart.
- View cart items, quantities, and total price.
- Update product quantities.
- Remove products from the cart.
- Maintain separate shopping carts for authenticated users.

### 4. Order Management
- Create orders from shopping cart items.
- Generate unique order references.
- Review order details before confirmation.
- Confirm pending orders explicitly.
- View order history and order statuses.
- Cancel pending orders.

### 5. User Authentication
- User registration.
- Secure login and logout.
- Password hashing using PBKDF2-HMAC-SHA256.
- Unique email address validation.
- User-specific shopping cart and order data.
- User-specific conversation history.

### 6. Persistent Conversation Memory
- Automatically save user and assistant messages.
- Create new conversations.
- View previous conversations.
- Continue an existing conversation.
- Delete individual conversations.
- Maintain conversation history after restarting the application.

### 7. Conversational AI Assistant
- Understand natural-language shopping requests.
- Select appropriate tools based on user queries.
- Handle product search, comparison, cart operations, and order management.
- Answer general grocery-shopping questions.
- Provide conversational responses without unnecessarily invoking tools.

## 🧰 Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application development |
| LangChain | AI agent orchestration and tool calling |
| Groq | LLM inference |
| `openai/gpt-oss-120b` | Language model |
| Streamlit | Interactive chat interface |
| SQLite | Database and persistent storage |
| PBKDF2-HMAC-SHA256 | Password hashing |
| python-dotenv | Environment variable management |

## 🏗️ Application Architecture

```text
                    User
                      |
                      v
                Streamlit UI
                      |
             +--------+--------+
             |                 |
             v                 v
       Authentication     Chat Interface
             |                 |
             v                 v
           SQLite         LangChain Agent
                               |
                               v
                            Groq LLM
                               |
                       Tool Selection
                               |
           +-------------------+-------------------+
           |                   |                   |
           v                   v                   v
      Product Search      Comparison          Cart & Orders
           |                   |                   |
           +-------------------+-------------------+
                               |
                               v
                             SQLite
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
           User Data                  Conversation Memory
```

## 📁 Project Structure

```text
AI-Shopping-Agent/
│
├── app.py              # Streamlit UI, authentication and chat interface
├── agent.py            # LangChain agent and system prompt
├── auth.py             # User registration, login and authentication
├── memory.py           # Persistent conversation memory
├── setup_db.py         # Database setup and sample product data
├── tools.py            # Product, comparison, cart and order tools
├── reviews_api.py      # Product rating and review aggregation
├── requirements.txt    # Project dependencies
├── .env                # Environment variables (not committed)
├── .gitignore
└── README.md
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

**macOS / Linux**

```bash
python3 -m venv .venv

source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv

.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key

# Optional: Custom SQLite database path
DB_PATH=../resources/store.db
```

Replace `your_groq_api_key` with your actual Groq API key.

**Important:** Never commit your `.env` file or expose your API key publicly.

### 5. Run the Application

```bash
streamlit run app.py
```

Open the local URL displayed in your terminal.

### 6. Register and Login

1. Open the application.
2. Register a new account.
3. Log in using your credentials.
4. Start interacting with the AI Shopping Agent.

## 💬 Example Queries

### Product Search

```text
Find organic honey under $20 with a 4.5+ rating.

Show me organic snacks under $10.

Find the best-rated coffee.
```

### Product Comparison

```text
Compare products 1, 2 and 3.

Which product is cheaper?

Which product has the highest rating?
```

### Shopping Cart

```text
Add product 1 to my cart.

Show my shopping cart.

Change the quantity of product 1 to 3.

Remove product 1 from my cart.
```

### Order Management

```text
Create an order from my cart.

Show my order history.

Confirm order ORD-000001.

Cancel order ORD-000001.
```

Use the actual product IDs and order references returned by the application.

### General Questions

```text
What should I consider when buying organic honey?

What is the difference between organic and regular products?

How can I choose a good-quality coffee?
```

## 🗄️ Database Design

The application uses SQLite for persistent storage.

| Table | Purpose |
|---|---|
| `users` | Stores registered user information and password hashes |
| `products` | Stores grocery product catalog |
| `reviews` | Stores product reviews and ratings |
| `cart_items` | Stores user-specific shopping cart items |
| `customer_orders` | Stores customer orders and statuses |
| `customer_order_items` | Stores individual items belonging to orders |
| `conversations` | Stores conversation metadata associated with users |
| `conversation_messages` | Stores user and assistant messages |

The database is initialized automatically by the application when required.

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | API key for Groq model access |
| `DB_PATH` | No | Custom SQLite database file path |

## 🔐 Security Considerations

- Passwords are hashed using PBKDF2-HMAC-SHA256 rather than stored as plain text.
- Each authenticated user has a separate shopping cart.
- Order history and conversation history are scoped to the authenticated user.
- API credentials are managed through environment variables.
- This project is intended as a learning and demonstration application, not a production-ready e-commerce platform.


## 👨‍💻 Author

**Shrikant Kumar**

[GitHub – ShrikantKumar123](https://github.com/ShrikantKumar123)

---

If you find this project interesting, consider giving the repository a ⭐.