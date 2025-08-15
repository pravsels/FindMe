
# Find Me

Find if your face has been posted to a Subreddit. Only searches the latest 50 posts. 

<img width="500" height="480" alt="Screenshot 2025-08-15 at 16 27 15" src="https://github.com/user-attachments/assets/8c2983c6-64aa-4066-8115-c4d2de8111f4" />

## Setup

Create a conda env

```
conda create -n findme python=3.10 -y
conda activate findme
```

Install requirements

```
pip install -r requirements.txt
```

Create a file named .env and add Reddit creds:
```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
```

Run server locally
```
uvicorn server:app --reload
```

Open http://localhost:8000

First run will download InsightFace models to ~/.insightface/ (few hundred MBs).
