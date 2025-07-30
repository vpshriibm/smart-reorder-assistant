# app/main.py

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.agents.ingestion import read_sales_csv
from app.agents.forecasting import forecast_sales
from app.agents.reorder import apply_reorder_trigger
from app.agents.optimizer import optimize_reorder_plan
from app.db import get_connection, create_forecast_table, save_forecast_df
import pandas as pd
import traceback

app = FastAPI()

@app.on_event("startup")
def startup():
    conn = get_connection()
    create_forecast_table(conn)
    conn.close()

@app.post("/forecast")
async def forecast_endpoint(
    file: UploadFile = File(...),
    reorder_mode: str = Form("fixed"),
    threshold: float = Form(50),
    buffer: float = Form(10),
    stock_file: UploadFile = File(None),
    constraint_file: UploadFile = File(None)
):
    try:
        contents = await file.read()
        df = read_sales_csv(contents)  # Default expects ds, sku, y
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"CSV parsing failed: {str(e)}")

    try:
        result = forecast_sales(df)
        historical_df = result["historical"]
        forecast_df = result["forecast"]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Forecasting failed: {str(e)}")

    stock_df = None
    if stock_file:
        try:
            stock_contents = await stock_file.read()
            stock_df = read_sales_csv(stock_contents, expected_cols=["sku", "stock"])
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Stock CSV parsing failed: {str(e)}")

    if constraint_file:
        try:
            constraint_contents = await constraint_file.read()
            constraint_df = read_sales_csv(constraint_contents, expected_cols=["sku", "min_qty", "stockout_risk"])
            forecast_df = forecast_df.merge(constraint_df, on="sku", how="left")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Constraint CSV parsing failed: {str(e)}")

    try:
        forecast_df = apply_reorder_trigger(forecast_df, reorder_mode, threshold, stock_df, buffer)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Applying reorder logic failed: {str(e)}")

    if "unit_cost" not in forecast_df.columns:
        forecast_df["unit_cost"] = 100.0
    if "min_qty" not in forecast_df.columns:
        forecast_df["min_qty"] = 1
    if "stockout_risk" not in forecast_df.columns:
        forecast_df["stockout_risk"] = 0.5

    try:
        conn = get_connection()
        save_forecast_df(conn, forecast_df)
        conn.close()
    except Exception as e:
        traceback.print_exc()

    forecast_df["ds"] = forecast_df["ds"].astype(str)
    historical_df["ds"] = historical_df["ds"].astype(str)

    return JSONResponse(content={
        "historical": historical_df.to_dict(orient="records"),
        "forecast": forecast_df[["ds", "sku", "yhat", "yhat_lower", "yhat_upper", "reorder_trigger", "unit_cost", "min_qty", "stockout_risk"]].to_dict(orient="records")
    })

@app.post("/optimize")
async def optimize_endpoint(data: dict):
    try:
        forecast_df = pd.DataFrame(data["forecast"])
        if "unit_cost" not in forecast_df.columns:
            forecast_df["unit_cost"] = 100.0
        if "min_qty" not in forecast_df.columns:
            forecast_df["min_qty"] = 1
        if "stockout_risk" not in forecast_df.columns:
            forecast_df["stockout_risk"] = 0.5

        optimized_df = optimize_reorder_plan(forecast_df)
        return JSONResponse(content=optimized_df.to_dict(orient="records"))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

