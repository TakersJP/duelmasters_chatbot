import pandas as pd
import chromadb
from chromadb.config import Settings
import ollama
import json
from pathlib import Path
import time

class DuelMastersDataProcessor:
    def __init__(self):
        # スクリプトの場所を基準にパスを設定
        script_dir = Path(__file__).parent
        self.data_dir = script_dir / "data"
        self.cards_df = None
        self.keywords = []
        self.tags = []
        
        # ChromaDB クライアント初期化
        self.chroma_client = chromadb.PersistentClient(
            path=str(script_dir / "chroma_db"),
            settings=Settings(anonymized_telemetry=False)
        )
        
    def load_data(self):
        """CSVとテキストファイルを読み込み"""
        print("データを読み込み中...")
        
        # CSVファイル読み込み（複数の方法を試す）
        csv_path = self.data_dir / "cards.csv"
        
        # 方法1: pythonエンジンで読み込み
        try:
            self.cards_df = pd.read_csv(
                csv_path,
                encoding="utf-8",
                on_bad_lines='skip',  # 問題のある行をスキップ
                engine='python',  # pythonエンジンを使用
                quotechar='"',
                skipinitialspace=True
            )
            print(f"✅ カードデータ: {len(self.cards_df)}枚読み込み完了")
            
        except Exception as e:
            print(f"⚠️  方法1失敗: {e}")
            # 方法2: 手動で行ごとに読み込み
            print("方法2で再試行中...")
            try:
                import csv
                cards_data = []
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader, 1):
                        try:
                            cards_data.append(row)
                        except Exception as row_error:
                            print(f"⚠️  行 {i} をスキップ: {row_error}")
                
                self.cards_df = pd.DataFrame(cards_data)
                print(f"✅ カードデータ: {len(self.cards_df)}枚読み込み完了（方法2）")
                
            except Exception as e2:
                print(f"❌ すべての方法で失敗: {e2}")
                raise
        
        # カラム名を確認
        print(f"カラム: {list(self.cards_df.columns)}")
        print(f"サンプル:\n{self.cards_df.head(2)}")
        
        # keywords.txt 読み込み
        with open(self.data_dir / "keywords.txt", "r", encoding="utf-8") as f:
            self.keywords = [line.strip() for line in f if line.strip()]
        print(f"✅ キーワード: {len(self.keywords)}件読み込み完了")
        
        # tags.txt 読み込み（エンコーディング問題があるので修正）
        try:
            with open(self.data_dir / "tags.txt", "r", encoding="utf-8") as f:
                self.tags = [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            # エンコーディング自動検出
            import chardet
            with open(self.data_dir / "tags.txt", "rb") as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding']
            with open(self.data_dir / "tags.txt", "r", encoding=encoding) as f:
                self.tags = [line.strip() for line in f if line.strip()]
        print(f"✅ タグ: {len(self.tags)}件読み込み完了")
        
    def create_search_text(self, row):
        """各カードの検索用テキストを生成"""
        parts = []
        
        # カード名
        if pd.notna(row.get('card_name')):
            parts.append(f"カード名: {row['card_name']}")
        
        # 文明
        if pd.notna(row.get('civilization')):
            parts.append(f"文明: {row['civilization']}")
        
        # 種族
        if pd.notna(row.get('race')):
            parts.append(f"種族: {row['race']}")
        
        # カードタイプ
        if pd.notna(row.get('card_type')):
            parts.append(f"タイプ: {row['card_type']}")
        
        # コスト
        if pd.notna(row.get('cost')):
            parts.append(f"コスト: {row['cost']}")
        
        # パワー
        if pd.notna(row.get('power')):
            parts.append(f"パワー: {row['power']}")
        
        # テキスト（効果）
        if pd.notna(row.get('text')):
            parts.append(f"効果: {row['text']}")
        
        # タグ
        if pd.notna(row.get('tags')):
            parts.append(f"タグ: {row['tags']}")
        
        return "\n".join(parts)
    
    def generate_embeddings(self, text):
        """Ollamaでテキストをベクトル化"""
        try:
            response = ollama.embeddings(
                model='nomic-embed-text',
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            print(f"❌ エラー: {e}")
            return None
    
    def process_and_store(self, batch_size=100):
        """カードデータを処理してChromaDBに保存"""
        print("\nデータ処理を開始...")
        
        # コレクション作成（既存のものは削除）
        try:
            self.chroma_client.delete_collection("duel_masters_cards")
        except:
            pass
        
        collection = self.chroma_client.create_collection(
            name="duel_masters_cards",
            metadata={"description": "Duel Masters card database"}
        )
        
        total_cards = len(self.cards_df)
        processed = 0
        
        for i in range(0, total_cards, batch_size):
            batch = self.cards_df.iloc[i:i+batch_size]
            
            documents = []
            metadatas = []
            ids = []
            embeddings = []
            
            for idx, row in batch.iterrows():
                # 検索用テキスト生成
                search_text = self.create_search_text(row)
                documents.append(search_text)
                
                # メタデータ作成
                metadata = {
                    "card_name": str(row.get('card_name', '')),
                    "civilization": str(row.get('civilization', '')),
                    "card_type": str(row.get('card_type', '')),
                    "cost": str(row.get('cost', '')),
                    "power": str(row.get('power', '')),
                    "race": str(row.get('race', '')),
                }
                metadatas.append(metadata)
                
                # ID生成
                ids.append(f"card_{idx}")
                
                # ベクトル化
                embedding = self.generate_embeddings(search_text)
                if embedding:
                    embeddings.append(embedding)
                else:
                    # エラー時はダミーベクトル
                    embeddings.append([0.0] * 768)
                
                processed += 1
                if processed % 10 == 0:
                    print(f"進捗: {processed}/{total_cards} ({processed/total_cards*100:.1f}%)")
            
            # バッチ保存
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )
            
            # API制限対策（念のため）
            time.sleep(0.1)
        
        print(f"\n✅ 完了！ {processed}枚のカードをデータベースに保存しました")
        
    def test_search(self, query):
        """検索テスト"""
        print(f"\nテスト検索: '{query}'")
        
        collection = self.chroma_client.get_collection("duel_masters_cards")
        
        # クエリをベクトル化
        query_embedding = self.generate_embeddings(query)
        
        # 検索実行
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        print("\n検索結果:")
        for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0]), 1):
            print(f"\n【{i}】{metadata['card_name']}")
            print(f"文明: {metadata['civilization']} | タイプ: {metadata['card_type']}")
            print(f"コスト: {metadata['cost']} | パワー: {metadata['power']}")
            print(f"---")

def main():
    print("=" * 50)
    print("デュエル・マスターズ カードデータベース構築")
    print("=" * 50)
    
    processor = DuelMastersDataProcessor()
    
    # Step 1: データ読み込み
    processor.load_data()
    
    # Step 2: データ処理とベクトル化
    processor.process_and_store(batch_size=50)
    
    # Step 3: テスト検索
    processor.test_search("コスト5以上の革命チェンジ先のドラゴン")
    
    print("\nすべての処理が完了しました！")

if __name__ == "__main__":
    main()