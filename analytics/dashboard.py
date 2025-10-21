import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from clickhouse_driver import Client
import os

# --- Database Connection ---
CLICKHOUSE_HOST = os.environ.get('CLICKHOUSE_HOST', 'localhost')
client = Client(host=CLICKHOUSE_HOST)

def query_clickhouse(query):
    """Queries ClickHouse and returns a pandas DataFrame."""
    try:
        data, columns = client.execute(query, with_column_types=True)
        df = pd.DataFrame(data, columns=[c[0] for c in columns])
        return df
    except Exception as e:
        print(f"ClickHouse query failed: {e}")
        return pd.DataFrame() # Return empty dataframe on error

# --- Dash App Initialization ---
app = dash.Dash(__name__)
app.title = "Accounting Analytics Dashboard"

app.layout = html.Div(style={'backgroundColor': '#f0f2f5', 'fontFamily': 'Arial'}, children=[
    html.H1(
        "Real-Time Accounting Dashboard",
        style={'textAlign': 'center', 'color': '#333', 'padding': '20px'}
    ),
    
    html.Div(dcc.Graph(id='daily-volume-chart'), style={'padding': '10px'}),
    html.Div(dcc.Graph(id='transaction-count-chart'), style={'padding': '10px'}),
    
    dcc.Interval(
        id='interval-component',
        interval=30*1000, # Update every 30 seconds
        n_intervals=0
    )
])

# --- Callbacks for Live Updating Charts ---
@app.callback(
    Output('daily-volume-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_daily_volume(n):
    """Updates the daily transaction volume chart."""
    query = """
        SELECT
            kpi_date,
            sumMerge(total_volume) as total_sales
        FROM daily_kpi_summary
        WHERE kpi_date >= today() - 30
        GROUP BY kpi_date
        ORDER BY kpi_date
    """
    df = query_clickhouse(query)
    if df.empty:
        return px.line(title="No data available for Daily Transaction Volume")
        
    fig = px.bar(
        df,
        x='kpi_date',
        y='total_sales',
        title='Daily Transaction Volume (Last 30 Days)',
        labels={'kpi_date': 'Date', 'total_sales': 'Total Volume (GEL)'}
    )
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#333')
    return fig

@app.callback(
    Output('transaction-count-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_transaction_count(n):
    """Updates the daily transaction count chart."""
    query = """
        SELECT
            kpi_date,
            countMerge(transaction_count) as num_transactions
        FROM daily_kpi_summary
        WHERE kpi_date >= today() - 30
        GROUP BY kpi_date
        ORDER BY kpi_date
    """
    df = query_clickhouse(query)
    if df.empty:
        return px.line(title="No data available for Daily Transaction Count")

    fig = px.line(
        df,
        x='kpi_date',
        y='num_transactions',
        title='Daily Transaction Count (Last 30 Days)',
        labels={'kpi_date': 'Date', 'num_transactions': 'Number of Transactions'},
        markers=True
    )
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#333')
    return fig

# --- Main execution ---
if __name__ == '__main__':
    # To run this dashboard, you need to install dash, pandas, and clickhouse_driver:
    # pip install dash pandas clickhouse-driver
    app.run_server(debug=True, host='0.0.0.0', port=8050)
