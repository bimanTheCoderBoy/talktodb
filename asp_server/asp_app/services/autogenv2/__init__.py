"""
AutoGen v2 — coverage-driven candidate site generator.

Structure:
  orchestrator.py          Main entry: save_config + run_autogen_pipeline
  raster/                  BIL extraction, population weighting
  clustering/              DBSCAN / KMeans, spacing constraints
  network/                 PCI / TAC / RSI from project DB
  output/                  GDL XLSX generation
  utils/                   IID naming helpers
"""
