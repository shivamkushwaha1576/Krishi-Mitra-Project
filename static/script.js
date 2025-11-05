// This ensures the JS code runs only after the HTML is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    fetchWeather();
    fetchMarketPrices();
});

// 1. Function to fetch weather data
async function fetchWeather() {
    try {
        // Call our Python API (/api/weather)
        const response = await fetch('/api/weather');
        
        if (!response.ok) {
            throw new Error('Weather API response not ok');
        }

        const data = await response.json();

        // Find the 'weather-data' div in the HTML
        const weatherDiv = document.getElementById('weather-data');
        
        // Change the HTML to display the data
        weatherDiv.innerHTML = `
            <p><strong>Temperature:</strong> ${data.temperature}</p>
            <p><strong>Condition:</strong> ${data.condition}</p>
            <p><strong>Humidity:</strong> ${data.humidity}</p>
        `;
    } catch (error) {
        console.error('Error fetching weather:', error);
        if (document.getElementById('weather-data')) {
            document.getElementById('weather-data').innerHTML = '<p style="color: red;">Failed to load weather data. Please check your City in the dashboard.</p>';
        }
    }
}

// 2. Function to fetch market prices
async function fetchMarketPrices() {
    try {
        // Call our Python API (/api/market_prices)
        const response = await fetch('/api/market_prices');
        
        if (!response.ok) {
            throw new Error('Market API response not ok');
        }

        const data = await response.json(); // [{}, {}, {}]

        // Find the 'prices-body' (table body) in the HTML
        const pricesBody = document.getElementById('prices-body');
        pricesBody.innerHTML = ''; // Remove the "Loading..." text

        // Create a new row in the table for each crop
        data.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.crop}</td>
                <td>${item.price}</td>
            `;
            pricesBody.appendChild(row);
        });

    } catch (error) {
        console.error('Error fetching prices:', error);
        if (document.getElementById('prices-body')) {
            pricesBody.innerHTML = '<tr><td colspan="2" style="color: red;">Failed to load prices.</td></tr>';
        }
    }
}