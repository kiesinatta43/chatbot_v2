from app.documents import load_supported_documents
from app.retriever import build_index, save_index


def main() -> None:
    chunks = load_supported_documents()
    if not chunks:
        print("No supported documents found in src/.")
        return

    index = build_index(chunks)
    save_index(index)
    print(f"Indexed {len(chunks)} chunks from src/.")


if __name__ == "__main__":
    main()
