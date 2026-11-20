# lovecraft-corpus

A cleanly formatted JSONL corpus of H.P. Lovecraft's fiction, poetry, essays, and letters from [hplovecraft.com](https://hplovecraft.com) for ML-related purposes.

#### Corpus Size

| Category | Documents | Characters |
| :--- | ---: | ---: |
| essays | 8 | 502,431 |
| fiction | 105 | 8,177,709 |
| letters | 2 | 23,286 |
| poetry | 49 | 115,159 |
| **Total** | **164** | **8,818,585**  (~8.6 MB JSONL) |

#### Usage
The scraping script is made available for those who want to run it themselves.
```bash
pip install requests beautifulsoup4
python corpus.py
```

#### Schema

```json
{
  "id": "fiction/the-call-of-cthulhu",
  "category": "fiction",
  "title": "The Call of Cthulhu",
  "source": "[https://hplovecraft.com/writings/texts/fiction/cc.aspx](https://hplovecraft.com/writings/texts/fiction/cc.aspx)",
  "chars": 71342,
  "text": "..."
}
```

#### Loading with Hugging Face 

```python
from datasets import load_dataset

ds = load_dataset("json", data_files="data/lovecraft.jsonl", split="train")
```

### License & Disclaimer

The script is licensed under the [MIT License](LICENSE).

The dataset is compiled from [hplovecraft.com](https://hplovecraft.com) for research and educational purposes.
H.P. Lovecraft's works are widely considered to be in the public domain, though copyright status for certain letters or collaborative works may vary by jurisdiction.
If you are a rights holder and believe any included text infringes copyright, please open an issue and it will be removed promptly.
