// Sample data - In production, this would come from an API
const SAMPLE_DATA = {
    last_updated: new Date().toISOString(),
    stocks: [
        {
            ticker: "AAPL",
            name: "Apple Inc.",
            region: "US",
            current_price: 185.43,
            price_change: 2.34,
            price_change_percent: 1.28,
            confidence_score: 82,
            catalyst: "Strong Q4 earnings beat, new product launch imminent",
            analysis: "Breaking above 50-day MA on high volume. RSI showing strong momentum.",
            volume: 45678900,
            avg_volume: 34567000
        }
    ]
};

class StockDashboard {
    constructor() {
        this.stocks = [];
        this.filteredStocks = [];
        this.currentRegion = 'all';
        this.searchTerm = '';
        
        this.init();
    }

    async init() {
        await this.loadData();
        this.render();
        this.setupEventListeners();
    }

    async loadData() {
        try {
            console.log("Loading stock data...");
            
            // Try to load from the generated JSON file
            const response = await fetch('./data/processed/latest_stocks.json');
            
            if (response.ok) {
                const data = await response.json();
                console.log("Data loaded successfully:", data);
                
                if (data.stocks && data.stocks.length > 0) {
                    this.stocks = data.stocks;
                    this.lastUpdated = data.last_updated;
                    console.log(`Loaded ${this.stocks.length} stocks`);
                } else {
                    throw new Error('No stocks in data');
                }
            } else {
                throw new Error('Failed to load data file');
            }
        } catch (error) {
            console.error('Error loading data:', error);
            console.log('Using sample data as fallback');
            
            // Use sample data as fallback
            this.stocks = SAMPLE_DATA.stocks;
            this.lastUpdated = SAMPLE_DATA.last_updated;
            
            // Show error message to user
            this.showErrorMessage('Using sample data - real data will be available after next update');
        }
        
        this.filteredStocks = [...this.stocks];
        this.updateLastUpdated();
    }

    showErrorMessage(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.innerHTML = `<p>⚠️ ${message}</p>`;
            errorDiv.style.display = 'block';
        }
    }

    updateLastUpdated() {
        const updateTime = document.getElementById('update-time');
        if (this.lastUpdated) {
            const date = new Date(this.lastUpdated);
            updateTime.textContent = date.toLocaleString('en-US', { 
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } else {
            updateTime.textContent = 'Loading...';
        }
    }

    setupEventListeners() {
        // Region filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentRegion = e.target.dataset.region;
                this.applyFilters();
            });
        });

        // Search input
        const searchInput = document.getElementById('stock-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value.toLowerCase();
                this.applyFilters();
            });
        }
    }

    applyFilters() {
        this.filteredStocks = this.stocks.filter(stock => {
            const regionMatch = this.currentRegion === 'all' || stock.region === this.currentRegion;
            const searchMatch = !this.searchTerm || 
                stock.ticker.toLowerCase().includes(this.searchTerm) ||
                (stock.company_name && stock.company_name.toLowerCase().includes(this.searchTerm));
            return regionMatch && searchMatch;
        });
        this.render();
    }

    render() {
        this.renderStats();
        this.renderStockGrid();
        this.hideLoading();
    }

    renderStats() {
        const totalStocks = this.filteredStocks.length;
        const highConfidence = this.filteredStocks.filter(s => s.confidence_score >= 70).length;
        const avgScore = totalStocks > 0 
            ? Math.round(this.filteredStocks.reduce((sum, s) => sum + s.confidence_score, 0) / totalStocks)
            : 0;

        // Update stats
        const totalElement = document.getElementById('total-stocks');
        const highConfElement = document.getElementById('high-confidence');
        const avgScoreElement = document.getElementById('avg-score');
        
        if (totalElement) totalElement.textContent = totalStocks;
        if (highConfElement) highConfElement.textContent = highConfidence;
        if (avgScoreElement) avgScoreElement.textContent = avgScore;
    }

    renderStockGrid() {
        const grid = document.getElementById('stock-grid');
        if (!grid) return;
        
        if (this.filteredStocks.length === 0) {
            grid.innerHTML = '<div class="no-results">No stocks match your filters</div>';
            grid.style.display = 'block';
            return;
        }

        grid.innerHTML = this.filteredStocks.map(stock => `
            <div class="stock-card" data-region="${stock.region}">
                <div class="stock-header">
                    <div class="stock-ticker">${stock.ticker}</div>
                    <div class="stock-region">${stock.region}</div>
                </div>
                <div class="stock-name">${stock.company_name || stock.ticker}</div>
                
                <div class="stock-price">$${stock.current_price?.toFixed(2) || 'N/A'}</div>
                <div class="price-change ${(stock.price_change_percent >= 0) ? 'positive' : 'negative'}">
                    ${stock.price_change_percent >= 0 ? '+' : ''}${stock.price_change_percent?.toFixed(2) || '0.00'}%
                </div>

                <div class="confidence-score">
                    <div class="score-bar">
                        <div class="score-fill ${this.getScoreClass(stock.confidence_score)}" 
                             style="width: ${stock.confidence_score || 0}%"></div>
                    </div>
                    <div class="score-text">
                        Confidence Score: <strong>${stock.confidence_score || 0}/100</strong>
                    </div>
                </div>

                <div class="catalyst">
                    <div class="catalyst-title">📊 Analysis</div>
                    <div>${stock.analysis || 'Technical analysis in progress'}</div>
                </div>

                ${stock.catalyst ? `
                <div class="analysis">
                    <strong>Catalyst:</strong> ${stock.catalyst}
                </div>
                ` : ''}

                ${stock.data_source ? `
                <div class="data-source">
                    <small>Source: ${stock.data_source}</small>
                </div>
                ` : ''}
            </div>
        `).join('');

        grid.style.display = 'grid';
    }

    getScoreClass(score) {
        if (score >= 70) return 'score-high';
        if (score >= 50) return 'score-medium';
        return 'score-low';
    }

    hideLoading() {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new StockDashboard();
});
