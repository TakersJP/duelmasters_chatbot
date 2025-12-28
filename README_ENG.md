# Duel Masters AI Chatbot

This project is an **AI chatbot for searching Duel Masters cards**.

"Was there a card that could do this?"  
"I want to find a Dragon with *Kakumei Change* that costs 8 or more"

When you have questions like these, instead of checking cards one by one, this tool lets you **find cards that match your conditions in a conversational manner**.

In the future, it aims to become a **tool that makes card searches more intuitive and faster**.

---

## Development Status as of December 29, 2025

### Completed Features

#### 1. Search System
Achieved high-precision search with a **two-stage search process**:

1. **Condition Extraction (using LLM)**
   - Automatically extracts search conditions from queries
   - Example: "5-cost *Kakumei Change* Dragon" → Cost=5, Keyword=*Kakumei Change*, Race=Dragon

2. **Filtering & Vector Search**
   - Narrows down candidates with strict conditions
   - Ranks by vector similarity
   - Automatically assigns bonus to condition-matching cards

#### 2. Discord Bot Integration
Implemented a bot that enables card searches on Discord:
- `/search` command for searching
- Pagination feature (displays 5 cards at a time)
- `/help` command to display usage instructions

## Technology Stack

### Data Management
- **Pandas**: Card data management and filtering
- **ChromaDB**: Vector database (for search)
- **CSV**: Card data persistence

### AI & Search
- **Ollama** (Local): Condition extraction by LLM (llama3.1:8b)
- **nomic-embed-text**: Text vectorization
- **Search**: Condition filtering + vector similarity

### Discord Bot
- **discord.py**: Discord API integration
- **app_commands**: Slash command implementation

## How Search Works

### 1. Query Analysis (LLM)
```
User: "5-cost Kakumei Change Dragon"
    ↓
LLM extracts:
{
  "cost_min": 5,
  "cost_max": 5,
  "keywords": ["Kakumei Change"],
  "race_keywords": ["Dragon"]
}
```

### 2. Filtering
```
11,244 cards
  → Only cost 5
  → Only with Kakumei Change
  → Only Dragon race
  ↓
Narrowed down to about 50 cards
```

### 3. Vector Search
```
50 candidates
  → Ranked by vector similarity
  → Condition match bonus applied
  ↓
Final result: Top 50
```

## Search Examples

### Example 1: Basic Search
```
/search 5-cost Kakumei Change Dragon
```
→ Displays cards with cost 5, *Kakumei Change* ability, and Dragon race

### Example 2: Search Using Slang Terms
```
/search Cyber cards that can do Mekurade
```
→ Displays Cyber race cards with Mekurade effect

## Discord Usage Example

<img width="1314" height="1050" alt="image" src="https://github.com/user-attachments/assets/c2fde562-af63-4f1d-ae42-48055e01edc4" />

---

## Development Status as of December 25, 2025

#### • Card Data Scraping
Card information is retrieved from the official website and saved as data including card names, text, etc.

#### • Data Storage
Retrieved card information is managed in CSV / database format.

## About Web Scraping

This project retrieves card information from the official Duel Masters website for the purpose of implementing card search functionality.
https://dm.takaratomy.co.jp/card/

The main information retrieved includes:

- Card name  
- Card text  
- Cost  
- Civilization  
- Race  

※ Card images are not retrieved or distributed.  
※ Not intended for commercial use.

### About Copyright and Site Policy

TAKARA TOMY's site policy is described at:

https://www.takaratomy.co.jp/utility/sitepolicy/

The "About Copyright" section in the site policy states:

> The copyright and other rights to the text, images, videos, games, trademarks, portraits, etc. (hereinafter referred to as "Web Data") on our website belong to the Company, the original author, or other rights holders. Web Data may not be used without the permission of the Company, the original author, or other rights holders, except when used by corporations for non-profit purposes, for personal use, or as otherwise permitted by copyright law.

This project uses data for research and educational purposes in card search within the scope of **non-profit, individual development**.

Therefore, this project is introduced and published based on the above site policy.

**If you undertake similar efforts with other trading card games, please make sure to check the site policy and terms of use established for each official website before implementation.**

## Technology Stack

### Web Scraping
- **Selenium**: Data retrieval from dynamic web pages
- **BeautifulSoup**: HTML parsing
- **Requests**: HTTP communication

## Screenshots During Scraping

As shown in the images below, **card information being retrieved (such as card names) is displayed sequentially in the terminal** during scraping execution.

This allows real-time confirmation of processing progress and retrieval status.

<img width="343" height="345" alt="Screenshot 2025-12-25 at 14 47 33" src="https://github.com/user-attachments/assets/cb40cf79-9dcc-4286-9d57-2e15829225f0" />

Also, **when a duplicate card that has already been retrieved appears, "Skip" is displayed in the terminal to prevent duplicate retrieval**.

<img width="333" height="328" alt="Screenshot 2025-12-25 at 14 52 29" src="https://github.com/user-attachments/assets/db106029-9a95-4a59-ac2d-c3747d373154" />

---

## Notes

- This project is **unofficial and individually developed**
- Duel Masters is copyrighted by TAKARA TOMY Co., Ltd.
- Not intended for commercial use
