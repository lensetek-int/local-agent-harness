"""Upload asadeltek-indo-tax-3b.gguf langsung dari Colab ke Hugging Face menggunakan env HF_TOKEN."""

import os
from huggingface_hub import HfApi


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN environment variable belum diset.")

    api = HfApi(token=token)
    api.create_repo(repo_id="lensetek/asadeltek-indo-tax-3b", repo_type="model", private=False, exist_ok=True)
    api.upload_file(
        path_or_fileobj="/content/asadeltek-indo-tax-3b.gguf",
        path_in_repo="asadeltek-indo-tax-3b.gguf",
        repo_id="lensetek/asadeltek-indo-tax-3b",
        repo_type="model",
        commit_message="Upload asadeltek-indo-tax-3b.gguf (Q4_K_M, 8/8 held-out accuracy)",
    )
    print("HF_PLAN_C_GGUF_UPLOADED_OK", flush=True)


if __name__ == "__main__":
    main()
