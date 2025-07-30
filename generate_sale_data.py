import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Config
start_date = datetime.today() - timedelta(days=90)
dates = [start_date + timedelta(days=i) for i in range(90)]
sales = np.random.poisson(lam=50, size=90)  # Poisson-distributed sales data

df = pd.DataFrame({
    "date": [d.strftime('%Y-%m-%d') for d in dates],
    "sales": sales
})

# Save to CSV
df.to_csv("sample_sales_data.csv", index=False)
print("✅ sample_sales_data.csv generated!")

