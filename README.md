# Stratify - Trading Strategy Testing & Execution Platform

Stratify is a comprehensive trading strategy testing and execution platform that allows you to backtest, paper trade, and live trade algorithmic strategies with OANDA. Built with modern web technologies, Stratify provides a user-friendly interface for developing, testing, and deploying trading strategies.

**Author:** Altaz Punja  
**Contact:** altazp@gmail.com | apunja@uwaterloo.ca

> **Live Demo:** Stratify is currently deployed at [https://strat-tester-nine.vercel.app/paper-trading](https://strat-tester-nine.vercel.app/paper-trading) (Vercel + Oracle Cloud).  
> _Note: Dashboard access is password-protected. **Contact altazp@gmail.com or apunja@uwaterloo.ca for the password** if you'd like to try it out!_

## Features

### Back Testing
- Test strategies on historical market data
- Comprehensive performance metrics (Total Return, Max Drawdown, CAGR, Profit Factor, Win Rate)
- Interactive equity curve visualization
- Trade history analysis
- Support for multiple instruments and timeframes
- Customizable strategy parameters

### Paper Trading
- Simulate trading with OANDA demo accounts
- Real-time position tracking
- Session management (start, stop, pause, resume)
- Multiple account support
- Real-time P&L updates via WebSocket
- Trade history and position management
- Account balance and equity tracking

### Live Trading
- Execute strategies with real OANDA accounts
- Same features as paper trading with live market execution
- Risk management controls
- Real-time monitoring and alerts
- **Live Trading Toggle Switch**: Access live trading features via the Settings menu in the header. Use the "Enable Live Trading" toggle to enable/disable access to live trading functionality. When enabled, you'll be redirected to the Live Trading page where you can manage live trading sessions with real OANDA accounts.

### Video Tutorials
**Backtest**
https://github.com/user-attachments/assets/7e16c8d3-1ac0-4aec-9093-3355601d1f40

**Paper Trading**
https://github.com/user-attachments/assets/403cb428-ca9e-4e6c-8d51-ee85b6772420

**Live Trading**
https://github.com/user-attachments/assets/f79c9e15-773f-403a-9ee8-d4539c628d18


### Strategy Management
- Multiple built-in strategies:
  - Custom EMA Strategy
  - Donchian Channel
  - Mean Reversion
  - Alpha Fusion
- Plugin-based architecture for custom strategies
  - Follow the template in base.py and any example strategy
- Strategy parameter customization
- Preset configurations

## Tech Stack

### Frontend
- **Next.js 15** - React framework with App Router
- **React 19** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS 4** - Styling
- **ApexCharts** - Data visualization
- **WebSocket** - Real-time updates

### Backend
- **FastAPI** - Python web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **WebSockets** - Real-time communication
- **OANDA API** - Trading integration

## Prerequisites

- **Node.js** 18.x or later (20.x recommended)
- **Python** 3.9 or later
- **OANDA Account** (for paper/live trading)
  - Practice account for paper trading
  - Live account for live trading

## API Documentation

Access the interactive API documentation at:
- **Swagger UI**: [http://40.233.115.48:8000/docs](http://40.233.115.48:8000/docs)
- **ReDoc**: [http://40.233.115.48:8000/redoc](http://40.233.115.48:8000/redoc)



## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Strat_Tester
```

### 2. Backend Setup

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt


### 3. Backend Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

```env
# OANDA API Configuration
OANDA_PRACTICE_API_KEY=your_practice_api_key_here
OANDA_HOST=https://api-fxpractice.oanda.com
OANDA_LIVE_API_KEY=your_live_api_key_here  # Optional, for live trading
OANDA_LIVE_HOST=https://api-fxtrade.oanda.com # Optional, for live trading


**Getting OANDA API Keys:**
1. Sign up for an OANDA account at [OANDA.com](https://www.oanda.com)
2. Navigate to Manage API Access in your account settings
3. Generate a practice API key for paper trading
4. (Optional) Generate a live API key for live trading

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
# or
yarn install

# Create a .env.local file
```

### 5. Frontend Environment Variables

Create a `.env.local` file in the `frontend/` directory:

```env
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000

# Admin password for login (optional, set if you want password protection)
ADMIN_PASSWORD=your_secure_password_here
```

For production deployment, update `NEXT_PUBLIC_BACKEND_URL` to your backend server URL.

## Running the Application

### Start the Backend

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://127.0.0.1:8000`

### Start the Frontend

```bash
cd frontend
npm run dev
# or
yarn dev
```

The frontend will be available at `http://localhost:3000`

### Access the Application

1. Open your browser and navigate to `http://localhost:3000`
2. If you set `ADMIN_PASSWORD`, you'll be prompted to enter it
3. You'll be redirected to the dashboard

## Usage

### Back Testing

1. Navigate to **Back Testing** from the sidebar
2. Select a strategy from the dropdown
3. Choose an instrument (e.g., EUR_USD, GBP_USD)
4. Select a timeframe (M15, H1, D, etc.)
5. Configure strategy parameters
6. Choose time range:
   - **Lookback**: Number of bars to test
   - **Date Range**: Specific start and end dates
7. Click **Run Backtest**
8. Review results:
   - Equity curve chart
   - Performance metrics
   - Trade history

### Paper Trading

1. Navigate to **Paper Trading** from the sidebar
2. View your OANDA demo accounts
3. Click on an account to open the management modal
4. Create a new trading session:
   - Select a strategy
   - Choose instrument and timeframe
   - Set position size limits
   - Configure strategy parameters
5. Start the session
6. Monitor:
   - Real-time positions
   - P&L updates
   - Trade history
   - Account balance

### Live Trading

⚠️ **Warning**: Live trading uses real money. Use with caution!

1. **Enable Live Trading**: Click on the **Settings** menu in the header and toggle the **"Enable Live Trading"** switch. This will enable access to live trading features and redirect you to the Live Trading page.
2. Ensure your live OANDA API key is configured in the backend environment variables (`OANDA_LIVE_API_KEY` and `OANDA_LIVE_HOST`)
3. Navigate to **Live Trading** from the sidebar (if not already redirected)
4. Follow the same steps as Paper Trading to create and manage live trading sessions
5. Monitor your live positions carefully - all trades will use real money!

**Note**: The live trading toggle preference is saved in your browser's localStorage. You can disable it at any time via the Settings menu.


## Deployment

### Frontend (Vercel)

1. Push your code to GitHub
2. Import project in Vercel
3. Set environment variables:
   - `NEXT_PUBLIC_BACKEND_URL`
   - `ADMIN_PASSWORD` (optional)
4. Deploy

### Backend

You can deploy the backend to most Python or container hosting services, such as:

- **Oracle Cloud**
- **DigitalOcean App Platform**
- **AWS/GCP/Azure**

Just run:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Make sure to set your environment variables on your hosting platform.


## Troubleshooting

### Backend Issues

**OANDA API Errors:**
- Verify your API key is correct
- Check that your account has the necessary permissions
- Ensure you're using the correct API endpoint (practice vs live)

**Port Already in Use:**
```bash
# Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
```

### Frontend Issues

**Build Errors:**
```bash
# Clear cache and reinstall
rm -rf node_modules .next
npm install
```

**Connection to Backend:**
- Verify `NEXT_PUBLIC_BACKEND_URL` is set correctly
- Check CORS settings in backend
- Ensure backend is running

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

⚠️ **Trading Disclaimer**: This software is for educational and research purposes. Trading involves substantial risk of loss. Past performance is not indicative of future results. Always test strategies thoroughly in paper trading before using real money. The authors and contributors are not responsible for any financial losses incurred from using this software.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the API documentation at http://40.233.115.48:8000/docs
- Contact altazp@gmail.com
