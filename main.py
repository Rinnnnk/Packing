# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.packing_controller import router as packing_router

app = FastAPI(
    title="定制家居智能板材分拣与装箱打包工作站",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 允许车间任意前端工位跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(packing_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)