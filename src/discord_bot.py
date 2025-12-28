import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from pathlib import Path
import sys

# search.py をインポート
sys.path.append(str(Path(__file__).parent))
from search import DuelMastersHybridSearch

# 環境変数を読み込み
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot の設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 検索システムを初期化（起動時に1回だけ）
searcher = None

@bot.event
async def on_ready():
    """Bot起動時の処理"""
    global searcher
    
    print(f'✅ {bot.user} としてログインしました')
    print(f'サーバー数: {len(bot.guilds)}')
    
    # 検索システムを初期化
    print("検索システムを初期化中...")
    try:
        searcher = DuelMastersHybridSearch()
        print("✅ 検索システム準備完了！")
    except Exception as e:
        print(f"❌ 検索システムの初期化エラー: {e}")
    
    # スラッシュコマンドを同期
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} 個のコマンドを同期しました")
    except Exception as e:
        print(f"❌ コマンド同期エラー: {e}")

@bot.tree.command(name="search", description="デュエル・マスターズのカードを検索")
@app_commands.describe(query="検索条件（例: コスト5以上の革命チェンジ先のドラゴン）")
async def search_card(interaction: discord.Interaction, query: str):
    """カード検索コマンド"""
    
    # 即座に応答（処理が長い場合のため）
    await interaction.response.defer()
    
    try:
        # 検索実行
        conditions = searcher.extract_search_conditions(query)
        
        if not conditions:
            await interaction.followup.send("❌ 検索条件の抽出に失敗しました")
            return
        
        filtered_df = searcher.filter_by_conditions(conditions)
        
        if len(filtered_df) == 0:
            await interaction.followup.send("❌ 条件に合うカードが見つかりませんでした")
            return
        
        ranked_df = searcher.rank_by_vector_search(filtered_df, query, top_k=50)
        
        # ページネーション用のViewクラス
        class PaginationView(discord.ui.View):
            def __init__(self, cards_df, per_page=5):
                super().__init__(timeout=180)  # 3分でタイムアウト
                self.cards_df = cards_df
                self.per_page = per_page
                self.current_page = 0
                self.max_page = (len(cards_df) - 1) // per_page
                
                # 5件以下ならボタンを削除
                if len(cards_df) <= per_page:
                    self.clear_items()
                
            def format_page(self):
                """現在のページを整形"""
                start = self.current_page * self.per_page
                end = start + self.per_page
                page_cards = self.cards_df.iloc[start:end]
                
                # 5件以下の場合はページ番号を表示しない
                if len(self.cards_df) <= self.per_page:
                    result_text = f"**検索結果: {len(self.cards_df)}件**\n\n"
                else:
                    result_text = f"**検索結果: {len(self.cards_df)}件** （ページ {self.current_page + 1}/{self.max_page + 1}）\n\n"
                
                for i, (idx, card) in enumerate(page_cards.iterrows(), start + 1):
                    result_text += f"**【{i}】{card['card_name']}**\n"
                    result_text += f"└ 文明: {card['civilization']} | タイプ: {card['card_type']}\n"
                    result_text += f"└ コスト: {card['cost']} | パワー: {card['power']}\n"
                    
                    if card['race'] and str(card['race']) != 'nan':
                        result_text += f"└ 種族: {card['race']}\n"
                    
                    # 効果テキストを短縮
                    if card['text'] and str(card['text']) != 'nan':
                        text = str(card['text'])[:100] + "..." if len(str(card['text'])) > 100 else str(card['text'])
                        result_text += f"└ 効果: {text}\n"
                    
                    result_text += "\n"
                
                return result_text
            
            @discord.ui.button(label="◀️ 前へ", style=discord.ButtonStyle.primary)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.current_page > 0:
                    self.current_page -= 1
                    await interaction.response.edit_message(content=self.format_page(), view=self)
                else:
                    await interaction.response.send_message("最初のページです", ephemeral=True)
            
            @discord.ui.button(label="次へ ▶️", style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.current_page < self.max_page:
                    self.current_page += 1
                    await interaction.response.edit_message(content=self.format_page(), view=self)
                else:
                    await interaction.response.send_message("最後のページです", ephemeral=True)
        
        # ページネーションビューを作成
        view = PaginationView(ranked_df)
        await interaction.followup.send(view.format_page(), view=view)
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")
        print(f"検索エラー: {e}")

@bot.tree.command(name="help", description="使い方を表示")
async def help_command(interaction: discord.Interaction):
    """ヘルプコマンド"""
    help_text = """
**デュエル・マスターズ 検索ボット**

**使い方:**
`/search` コマンドで検索ができます
**カード検索を行う場合は、BotとのDM（ダイレクトメッセージ）でご利用ください！**

**検索例:**
• `/search 5コスト以上の革命チェンジ先のドラゴン`
• `/search サイバーメクレイドできるカード`
• `/search 火文明のスピードアタッカーで3コスト以下のクリーチャー`
• `/search 自然の重量マッハファイター`
• `/search ハンデスできる軽量クリーチャー`
• `/search 軽量バウンス呪文`


**注意事項:**
• 検索には数秒かかる場合があります
• キーワードなどは略さず、できるだけ正確に入力してください。例：「5コス」ではなく「5コスト」
• 問題が発生した場合は管理者にお問い合わせください
    """
    await interaction.response.send_message(help_text)

# Bot を起動
if __name__ == "__main__":
    if not TOKEN:
        print("❌ エラー: DISCORD_TOKEN が .env ファイルに設定されていません")
    else:
        print("Bot を起動中...")
        bot.run(TOKEN)