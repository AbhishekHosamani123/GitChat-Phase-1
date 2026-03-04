import ingest
try:
    ingest.ingest_repository('https://github.com/pallets/click')
except Exception as e:
    import traceback
    traceback.print_exc()
