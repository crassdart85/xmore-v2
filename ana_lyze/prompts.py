get_recommendation = """You are getting news to extract data:
        - Which company is called, 
        - Classify them on the scale of -10 to +10 where -10 is the most negative news and +10.
        - What is the expected stock price movement in percentage.
        - Suggest the stock action: buy, hold, sell.
        - If news does not mention any company, return an empty list.
        - When the piece of news is neutral (0), suggest 'hold' as the stock action.
        Return the result in json format like this: 
        {
            'company': 'company_name',
            'score': score_value,
            'expected_stock_movement': expected_stock_movement,
            'stock_action': 'stock_action'
        }
        If multiple companies are mentioned, return a list of such json objects.
        If no company is mentioned, return an empty list."""
check_listed_companies = """Within this paragraph, you need to identify the companies that are publicly listed.
        here is the list of publicly listed companies with their stock symbols: {company_list}.
        Return the result as a json of company name and stock symbol as follows:
        {
            'company': 'company_name',
            'stock_symbol': 'stock_symbol'
        }
        If multiple publicly listed companies are mentioned, return a list of such json objects as below:
        [
            {
                'company': 'company_name_1',
                'stock_symbol': 'stock_symbol_1'
            },
            {
                'company': 'company_name_2',
                'stock_symbol': 'stock_symbol_2'
            }
        ]
        If no publicly listed companies are mentioned, return an empty list."""

summarize_news = """Summarize the following news article in 2-3 sentences, focusing on the key points and main events. 
    Avoid unnecessary details and ensure the summary is clear and concise."""


translate_to_english = """Translate the following text to English while preserving its original meaning and context. 
    Ensure that the translation is accurate and maintains the tone of the original text."""

translate_to_arabic = """Translate the following text to Arabic while preserving its original meaning and context. 
    Ensure that the translation is accurate and maintains the tone of the original text."""

get_gemma_response = """Extract the following information from the news article:
    - Identify and list all the companies mentioned in the article.
    - Check Which of them are publicly listed companies and its symbolwithin this list {company_list}.
    - Determine the sentiment of the article towards each company (positive, negative, neutral).
    - Extract any financial metrics or data points mentioned (e.g., stock prices, revenue figures, growth rates).
    - Identify any key events or developments discussed (e.g., mergers, acquisitions, product launches).
    - Summarize the overall impact of the news on the market or industry.
    Return the results in a structured JSON format with appropriate keys for each piece of information.
    Here is an example of the expected JSON structure:
    [
        {
        'company': 'company_name',
        'traded': 'yes',
        'traded_as': 'publicly listed/private',
        'stock_symbol': 'stock_symbol',
        'sentiment': 'positive/negative/neutral',
        'overall_impact': 'summary of impact',
        expected_stock_movement: 'percentage change',
        stock_action: 'buy/hold/sell'
        },
        {       
        'company': 'company_name_2',
        'traded': 'no',
        'traded_as': 'N/A',
        'stock_symbol': 'N/A',
        'sentiment': 'positive/negative/neutral',
        'overall_impact': 'summary of impact',
        expected_stock_movement: 'N/A',
        stock_action: 'N/A'
        }
    ]"""
