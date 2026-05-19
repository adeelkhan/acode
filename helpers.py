import subprocess
import ollama


def copy_to_clipboard(text: str) -> None:
    subprocess.run("pbcopy", input=text.encode(), check=True)


def check_ollama(model: str) -> tuple[bool, str, str]:
    """Returns (ok, title, error_message). Checks server reachability and model availability."""
    try:
        available = [m.model for m in ollama.list().models]
    except Exception:
        return False, "Backend Server Missing", (
            "Could not connect to the Ollama server.\n\n"
            "Make sure Ollama is installed and running:\n"
            "    ollama serve"
        )
    if not any(m == model or m.startswith(model.split(":")[0]) for m in available):
        return False, "Model Not Available", (
            f"Model '{model}' is not pulled on this machine.\n\n"
            f"Pull it first with:\n"
            f"    ollama pull {model}"
        )
    return True, "", ""


def get_model_info(model: str) -> dict:
    try:
        resp = ollama.show(model)
        details = resp.details
        mi = resp.modelinfo or {}
        arch = getattr(details, "family", "") or mi.get("general.architecture", "N/A")

        raw_count = mi.get("general.parameter_count", 0)
        if raw_count and isinstance(raw_count, int):
            if raw_count >= 1_000_000_000_000:
                params = f"{raw_count / 1e12:.1f}T".rstrip("0").rstrip(".")
            elif raw_count >= 1_000_000_000:
                params = f"{raw_count / 1e9:.0f}B"
            else:
                params = str(raw_count)
        else:
            params = getattr(details, "parameter_size", None) or "N/A"

        ctx_raw = mi.get(f"{arch}.context_length", 0)
        context = f"{ctx_raw // 1024}K" if ctx_raw >= 1024 else (str(ctx_raw) if ctx_raw else "N/A")

        emb_raw = mi.get(f"{arch}.embedding_length", 0)
        embedding = str(emb_raw) if emb_raw else "N/A"

        quant = getattr(details, "quantization_level", None) or "N/A"
        caps = [str(c) for c in (resp.capabilities or [])]

        return dict(arch=arch, params=params, context=context, embedding=embedding,
                    quant=quant, capabilities=caps)
    except Exception:
        return dict(arch="N/A", params="N/A", context="N/A", embedding="N/A",
                    quant="N/A", capabilities=[])
