# DocuRapi Cloud Development Copy

Salinan ini dibuat otomatis dari proyek lokal tanpa membawa:

- virtual environment;
- database SQLite;
- file `.env` dan secret;
- dokumen pengguna;
- hasil pemrosesan;
- log;
- release archive;
- folder backup.

## Menjalankan di Codespaces

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## Dependency

Sumber requirements: existing requirements.txt  
Jumlah baris: 6

## Aturan keamanan

Jangan commit:

- `.env`;
- `.env.production`;
- Server Key atau Client Key payment gateway;
- database;
- dokumen pengguna;
- hasil pemrosesan.

Gunakan GitHub Codespaces Secrets untuk credential pengembangan.
