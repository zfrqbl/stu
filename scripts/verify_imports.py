"""Verify that all locked Project Stu dependencies import successfully."""
from importlib import import_module

MODULES = [
    "fastapi", "uvicorn", "pydantic", "pydantic_settings", "loguru", 
    "requests", "dotenv", "mcp", "lancedb", "sentence_transformers", "aisuite",
]

def main() -> int:
    failed = []
    for module_name in MODULES:
        try:
            import_module(module_name)
            print(f"[OK]   {module_name}")
        except Exception as exc:
            failed.append(module_name)
            print(f"[FAIL] {module_name}: {exc}")

    if failed:
        print("\nDependency verification failed:")
        for m in failed: print(f"- {m}")
        return 1
    print("\nAll locked dependencies imported successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
