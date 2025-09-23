# On-Time Arrival Report (Streamlit)

A simple Streamlit app that reads your Excel file and reports **on-time arrivals by carrier** with flexible filters.

## Features
- Upload `.xlsx` (openpyxl engine).
- **Exclude-mode** filters for **Stop name** and **Carrier**.
- **Date range** filter on **Created time**.
- Select **on-time rule**: ≤0, ≤5, ≤10 minutes late, or **custom**.
- Uses **Stop arrival delta (minutes)** when available; otherwise computes from timestamps.
- Summary metrics, sortable table, and bar chart.
- Download filtered rows and the carrier summary as CSV.

## Expected Columns
Your Excel should contain the following headers (case & spacing are tolerant):
- Stop type, Stop name, Stop city, Stop state, Stop country  
- Stop planned arrival time start, Stop planned arrival time end  
- Stop actual arrival time, **Stop arrival delta (minutes)** (optional but preferred)  
- Stop actual departure time  
- Shipment ID, Shipment type  
- Current state, Current state reason  
- Latest milestone type, Latest milestone time  
- Exceptions, Open tasks  
- Current carrier  
- Vessel details - built in, Vessel details - used during  
- Origin, Origin city, Origin state, Origin country  
- Destination, Destination city, Destination state, Destination country  
- Destination estimated arrival time, Destination actual arrival time  
- Destination initial planned arrival time, Destination initial planned arrival end time  
- Destination latest planned arrival time, Destination latest planned arrival end time  
- Related orders  
- **Created time**  
- MSID

Minimum required for the report: **Stop name, Stop planned arrival time start, Stop actual arrival time, Current carrier, Created time**, and preferably **Stop arrival delta (minutes)** (or it will be computed).

## Run Locally
```bash
# 1) Create and activate a virtual environment (Python 3.10+ recommended)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run the app
streamlit run app.py
