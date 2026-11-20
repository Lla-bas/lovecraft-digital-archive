# lovecraft-comprehensive-corpus
[![Hugging Face Dataset](https://img.shields.io/badge/🤗%20Hugging%20Face-Gyran%2Flovecraft-yellow)](https://huggingface.co/datasets/Gyran/lovecraft-comprehensive-corpus)

A cleanly formatted JSONL corpus of H.P. Lovecraft's fiction, poetry, essays, and letters for ML-related purposes.

#### Corpus Size

| Category | Documents | Characters |
| :--- | ---: | ---: |
| essays | 47 | 656,628 |
| fiction | 105 | 8,177,709 |
| letters | 8 | 89,008 |
| poetry | 78 | 164,644 |
| **Total** | **238** | **9,087,989**  (~9 MB) |

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

### Quick Start

Load the pre-built dataset directly from [Hugging Face](https://huggingface.co/datasets/Gyran/lovecraft):

```python
from datasets import load_dataset

ds = load_dataset("Gyran/lovecraft-comprehensive-corpus")
```

### License & Disclaimer

The script is licensed under the [MIT License](LICENSE).

The dataset is compiled from [hplovecraft.com](https://hplovecraft.com) and [wikisource](https://en.wikisource.org/wiki/Author:Howard_Phillips_Lovecraft) for research and educational purposes.
H.P. Lovecraft's works are widely considered to be in the public domain, though copyright status for certain letters or collaborative works may vary by jurisdiction.
If you are a rights holder and believe any included text infringes copyright, please open an issue and it will be removed promptly.
