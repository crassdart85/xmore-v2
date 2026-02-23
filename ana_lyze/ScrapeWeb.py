class ScrapeArFin:
    def __init__(self):
        self.companies_site = (
            "https://www.arabfinance.com/Home/GetCompanyInfo?id=0&key="
        )
        self.shareholders_site = (
            "https://www.arabfinance.com/Home/GetShareholder?id=0&key="
        )
        self.listed_markets_site = (
            "https://www.arabfinance.com/Home/GetListedMarket?id=0&key="
        )
        self.share_performance_site = (
            "https://www.arabfinance.com/Home/GetPerformance?id=0&key="
        )

    def get_table_data(self, url: str) -> list:
        """Fetch data from the given URL and return it as a list of dictionaries.
        Args:
            url (str): The URL to fetch data from.
        Returns:
            list: A list of dictionaries containing the data.
        """
        import requests
        import json
        import pandas as pd

        response = requests.get(url)
        if response.status_code == 200:
            try:
                data = pd.DataFrame(response.json())
                return data
            except json.JSONDecodeError as e:
                print(f"JSON decoding error: {e}")
                return []
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            return []

    def get_companies(self) -> list:
        """Fetch the companies data table.
        Returns:
            list: A list of dictionaries containing the companies data.
        """
        return self.get_table_data(self.companies_site)

    def get_shareholders(self) -> list:
        """Fetch the shareholders data table.
        Returns:
            list: A list of dictionaries containing the shareholders data.
        """
        return self.get_table_data(self.shareholders_site)

    def get_listed_markets(self) -> list:
        """Fetch the listed markets data table.
        Returns:
            list: A list of dictionaries containing the listed markets data.
        """
        return self.get_table_data(self.listed_markets_site)

    def get_share_performance(self) -> list:
        """Fetch the share performance data table.
        Returns:
            list: A list of dictionaries containing the share performance data.
        """
        return self.get_table_data(self.share_performance_site)

    def get_all_data(self) -> dict:
        """Fetch all data tables and return them in a dictionary.
        Returns:
            dict: A dictionary containing all data tables.
        """
        return {
            "companies": self.get_companies(),
            "shareholders": self.get_shareholders(),
            "listed_markets": self.get_listed_markets(),
            "share_performance": self.get_share_performance(),
        }

    def get_data(self, required_data: list) -> dict:
        """Fetch specified data tables based on the required_data list.

        Args:
            required_data (list): List of data types to fetch. Possible values are:
                - "companies"
                - "shareholders"
                - "listed_markets"
                - "share_performance"
        Returns:
            dict: A dictionary containing the requested data tables.
        """
        data = {}
        if "companies" in required_data:
            data["companies"] = self.get_companies()
        if "shareholders" in required_data:
            data["shareholders"] = self.get_shareholders()
        if "listed_markets" in required_data:
            data["listed_markets"] = self.get_listed_markets()
        if "share_performance" in required_data:
            data["share_performance"] = self.get_share_performance()
        return data

    def save_data_to_parquet(self, data: dict, directory: str = "./data/") -> None:
        """Save data to Parquet files in the specified directory.
        Each key in the data dictionary will be used as the filename.

        Args:
            data (dict): A dictionary where keys are filenames and values are DataFrames.
            directory (str): The directory where the Parquet files will be saved.
        """
        import os
        import pandas as pd

        if not os.path.exists(directory):
            os.makedirs(directory)

        for key, df in data.items():
            if isinstance(df, pd.DataFrame):
                df.to_parquet(os.path.join(directory, f"{key}.parquet"), index=False)
            else:
                print(f"Data for {key} is not a DataFrame and cannot be saved.")

    def save_data_to_csv(self, data: dict, directory: str = "./data/") -> None:
        """Save data to CSV files in the specified directory.
        Each key in the data dictionary will be used as the filename.
        Args:
            data (dict): A dictionary where keys are filenames and values are DataFrames.
            directory (str): The directory where the CSV files will be saved.
        """
        import os
        import pandas as pd

        if not os.path.exists(directory):
            os.makedirs(directory)

        for key, df in data.items():
            if isinstance(df, pd.DataFrame):
                df.to_csv(os.path.join(directory, f"{key}.csv"), index=False)
            else:
                print(f"Data for {key} is not a DataFrame and cannot be saved.")


class ScrapeEnterprise:
    from datetime import datetime, date

    def __init__(self):
        self.uuid_url = "https://publisherv2.enterpriselive.projectsarea.com/api/FrontEndLayout/GetArchivedEditionsAndVerticalStoriesByWebsite"
        self.news_api = news_api = (
            "https://publisherv2.enterpriselive.projectsarea.com/api/FrontEndLayout/GetFullIssue?id={id}&languageId={lan_id}&websiteId=1"
        )
        self.default_cols = [
            "head_ar",
            "webHead_ar",
            "storyId_ar",
            "storyTagList_ar",
            "storyAudio_ar",
            "head_en",
            "webHead_en",
            "storyId_en",
            "webImageURL_en",
            "webStyle_en",
            "storyTagList_en",
            "storyAudio_en",
            "imagePosition_en",
            "c_storyContent_ar",
            "c_storyContent_en",
            "story_type_id",
            "story_category_id",
            #  'homePageHead_ar',
            #  'enTranslationRefId_ar',
            #  'storyContent_ar',
            #  'webImageURL_ar',
            #  'webStyle_ar',
            #  'storyTags_ar',
            # 'imagePosition_ar',
            #  'webExclude_ar',
            #  'noStoryHead_ar',
            #  'noSectionHead_ar',
            #  'poweredByProperties_ar',
            #  'sponsorList_ar',
            #  'verticalId_ar',
            #  'sectionStoryId_ar',
            #  'isSectionStory_ar',
            #  'homePageHead_en',
            #  'enTranslationRefId_en',
            #  'storyContent_en',
            #  'storyTags_en',
            #  'webExclude_en',
            #  'noStoryHead_en',
            #  'noSectionHead_en',
            #  'poweredByProperties_en',
            #  'sponsorList_en',
            #  'verticalId_en',
            #  'sectionStoryId_en',
            #  'isSectionStory_en',
        ]

    def get_month_ids(self, site: str, year: int, month_number: int):
        """Fetch news IDs for a specific month and year from the given site.
        Args:
            site (str): The URL to fetch data from.
            year (int): The year for which to fetch news IDs.
            month_number (int): The month (1-12) for which to fetch news IDs.
        Returns:
            pd.DataFrame: A DataFrame containing the news IDs for the specified month and year.
        """
        import requests
        import pandas as pd

        if not site:
            site = self.uuid_url
        en_body = {
            "websiteId": 1,
            "filter": {
                "editionStoryId": 1,
                "editionStoryTypeId": 1,
                "languageId": 2,
                "publishYear": year,
                "publishMonth": month_number,
            },
            "paginator": {"page": 1, "pageSize": "100"},
            "sorting": {
                "column": "publishDate",
                "direction": "desc",
                "sortingDirection": {"id": 1, "name": ""},
            },
            "requestLanguage": 2,
        }
        ar_body = {
            "websiteId": 1,
            "filter": {
                "editionStoryId": 1,
                "editionStoryTypeId": 1,
                "languageId": 1,
                "" "publishYear": year,
                "publishMonth": month_number,
            },
            "paginator": {"page": 1, "pageSize": "100"},
            "sorting": {
                "column": "publishDate",
                "direction": "desc",
                "sortingDirection": {"id": 1, "name": ""},
            },
            "requestLanguage": 1,
        }
        ar_df = pd.DataFrame(requests.post(site, json=ar_body).json()["dataList"])
        en_df = pd.DataFrame(requests.post(site, json=en_body).json()["dataList"])
        month_news_ids = pd.merge(
            ar_df, en_df, on="id", how="outer", suffixes=("_ar", "_en")
        )
        return month_news_ids

    def get_day_news_published(self, day_uuid: str, news_api: str):
        """Fetch news articles for a specific day using the provided UUID.
        Args:
            day_uuid (str): The UUID of the day to fetch news articles for.
        Returns:
            pd.DataFrame: A DataFrame containing the news articles for the specified day.
        """
        import requests
        import pandas as pd

        if not news_api:
            news_api = self.news_api
        ar_response = requests.get(news_api.format(id=day_uuid, lan_id=1))
        ar_df = pd.DataFrame(
            ar_response.json()["result"]["responseData"]["issueStoryList"]
        )
        en_response = requests.get(news_api.format(id=day_uuid, lan_id=2))
        en_df = pd.DataFrame(
            en_response.json()["result"]["responseData"]["issueStoryList"]
        )
        day_news = pd.merge(
            ar_df,
            en_df,
            left_on="enTranslationRefId",
            right_on="storyId",
            how="outer",
            suffixes=("_ar", "_en"),
        )
        return day_news

    def html_to_text(self, input_html: str) -> str:
        """Convert HTML content to plain text.
        Args:
            input_html (str): The HTML content to be converted.
        Returns:
            str: The plain text extracted from the HTML content.
        """
        from bs4 import BeautifulSoup

        return BeautifulSoup(input_html).get_text()

    def get_period_ids(self, period_start: datetime.date, period_end: datetime.date):
        """Fetch news articles for a specific month and year.
        Args:
            period_start (datetime.date): The start date of the period.
            period_end (datetime.date): The end date of the period.
        Returns:
            pd.DataFrame: A DataFrame containing the news articles for the specified month and year.
        """
        import pandas as pd
        from dateutil.relativedelta import relativedelta
        from tqdm import tqdm

        all_month_news_ids = pd.DataFrame()
        for month in tqdm(
            pd.date_range(start=period_start, end=period_end, freq="ME"),
            desc="Fetching monthly news IDs",
        ):
            try:
                month_news_ids = self.get_month_ids(
                    site=self.uuid_url,
                    year=month.year,
                    month_number=month.month,
                )
                all_month_news_ids = pd.concat(
                    [all_month_news_ids, month_news_ids], ignore_index=True
                )
            except Exception as e:
                print(f"Error fetching data for {month.strftime('%Y-%m')}: {e}")
        return all_month_news_ids

    def save_data_to_parquet(
        self, data: dict, directory: str = "./enterprise_data/"
    ) -> None:
        """Save data to Parquet files in the specified directory.
        Each key in the data dictionary will be used as the filename.

        Args:
            data (dict): A dictionary where keys are filenames and values are DataFrames.
            directory (str): The directory where the Parquet files will be saved.
        """
        import os
        import pandas as pd

        if not os.path.exists(directory):
            os.makedirs(directory)

        for key, df in data.items():
            if isinstance(df, pd.DataFrame):
                df.to_parquet(os.path.join(directory, f"{key}.parquet"), index=False)
            else:
                print(f"Data for {key} is not a DataFrame and cannot be saved.")

    def get_list_published_news(self, uuids: list):
        """Fetch news articles for a list of UUIDs.
        Args:
            uuids (list): A list of UUIDs to fetch news articles for.
        Returns:
            pd.DataFrame: A DataFrame containing the news articles for the specified UUIDs.
        """
        from tqdm import tqdm
        import pandas as pd

        First = True
        for uuid in tqdm(uuids, desc="Fetching news articles"):
            if First:
                try:
                    all_news = self.get_day_news_published(
                        day_uuid=uuid, news_api=self.news_api
                    )
                    First = False
                except Exception as e:
                    print(f"Error fetching news for UUID {uuid}: {e}")
            else:
                try:
                    day_news = self.get_day_news_published(
                        day_uuid=uuid, news_api=self.news_api
                    )
                    all_news = pd.concat([all_news, day_news], ignore_index=True)
                except Exception as e:
                    print(f"Error fetching news for UUID {uuid}: {e}")
        return all_news

    def store_published_news_json(self, uuids: list, path: str, news_api: str = None):
        """Fetch news articles for a list of UUIDs and store them as JSON files, with ar_ and en_ prefixes.
        Args:
            uuids (list): A list of UUIDs to fetch news articles for.
        Returns:
            pd.DataFrame: A DataFrame containing the news articles for the specified UUIDs.
        """
        from tqdm import tqdm
        import pandas as pd
        import requests

        for uuid in tqdm(uuids, desc="Fetching news articles"):
            try:
                if not news_api:
                    news_api = self.news_api
                ar_response = requests.get(news_api.format(id=uuid, lan_id=1))
                with open(f"{path}/ar_{uuid}.json", "w+", encoding="utf-8") as f:
                    f.write(ar_response.text)
            except Exception as e:
                print(f"Error fetching Arabic news for UUID {uuid}: {e}")
            try:
                en_response = requests.get(news_api.format(id=uuid, lan_id=2))
                with open(f"{path}/en_{uuid}.json", "w+", encoding="utf-8") as f:
                    f.write(en_response.text)
            except Exception as e:
                print(f"Error fetching news for UUID {uuid}: {e}")

    def get_html_content(self, df):
        """Extract HTML content from the DataFrame and add it as a new column.
        Args:
            df (pd.DataFrame): The DataFrame containing the news articles.
        Returns:
            pd.DataFrame: The DataFrame with an additional column for HTML content. If the HTML content is missing, the column will contain None.
        """
        import pandas as pd

        if "storyContent_ar" in df.columns:
            df["c_storyContent_ar"] = df["storyContent_ar"].apply(
                lambda x: self.html_to_text(x) if pd.notnull(x) else None
            )
            df = df.drop('storyContent_ar', axis=1)
        else:
            df["c_storyContent_ar"] = None

        if "storyContent_en" in df.columns:
            df["c_storyContent_en"] = df["storyContent_en"].apply(
                lambda x: self.html_to_text(x) if pd.notnull(x) else None
            )
            df = df.drop('storyContent_en', axis=1)
        else:
            df["c_storyContent_en"] = None

        return df

    def get_story_types(self, df):
        """Extract story types from the DataFrame and add it as a new column.
        Args:
            df (pd.DataFrame): The DataFrame containing the news articles.
        Returns:
            pd.DataFrame: The DataFrame with an additional column for story types. If the story type is missing, the column will contain None.
        """
        import pandas as pd
        import json

        if "storyType_ar" in df.columns and "storyType_en" in df.columns:
            df["story_type_id"] = df["storyType_ar"].apply(
                lambda x: x["id"] if pd.notnull(x) else None
            )
            df["story_type_name_ar"] = df["storyType_ar"].apply(
                lambda x: x["name"] if pd.notnull(x) else None
            )
            df["story_type_name_en"] = df["storyType_en"].apply(
                lambda x: x['name'] if pd.notnull(x) else None
            )
            story_types = (
                df[["story_type_id", "story_type_name_ar", "story_type_name_en"]]
                .drop_duplicates()
                .reset_index(drop=True)
            )
        elif "storyType_ar" in df.columns:
            df["story_type_id"] = df["storyType_ar"].apply(
                lambda x: x["id"] if pd.notnull(x) else None
            )
            df["story_type_name"] = df["storyType_ar"].apply(
                lambda x: x['name'] if pd.notnull(x) else None
            )
            story_types = (
                df[["story_type_id", "story_type_name"]]
                .drop_duplicates()
                .reset_index(drop=True)
            )
        elif "storyType_en" in df.columns:
            df["story_type_id"] = df["storyType_en"].apply(
                lambda x: x["id"] if pd.notnull(x) else None
            )
            df["story_type_name"] = df["storyType_en"].apply(
                lambda x: x['name'] if pd.notnull(x) else None
            )
            story_types = (
                df[["story_type_id", "story_type_name"]]
                .drop_duplicates()
                .reset_index(drop=True)
            )
        else:
            return None

        return story_types

    def get_story_categories(self, df):
        """Extract story categories from the DataFrame and add it as a new column.
        Args:
            df (pd.DataFrame): The DataFrame containing the news articles.
        Returns:
            pd.DataFrame: The DataFrame with an additional column for story categories. If the story category is missing, the column will contain None.
        """
        import pandas as pd
        import json

        if "storyCategory_ar" in df.columns and "storyCategory_en" in df.columns:
            story_categories = (
                df[["storyCategory_ar", "storyCategory_en"]]
                .drop_duplicates().dropna()
                .reset_index(drop=True)
                .reset_index().rename({'index':'category_id'}, axis=1)
            )
            df["story_category_id"] = df.merge(
                story_categories,
                on="storyCategory_ar",
                how="left",
                suffixes=('','_cats'),
            )["category_id"]#.rename({"category_id_cats": "category_id"}, axis=1)
        elif "storyCategory_ar" in df.columns:
            story_categories = (
                df["storyCategory_ar"].drop_duplicates().reset_index(drop=True)
            )
            df["story_category_id"] = df.join(
                story_categories.set_index("storyCategory_ar"),
                on="storyCategory_ar",
                how="left",
            )["story_category_id"]
        elif "storyCategory_en" in df.columns:
            story_categories = (
                df["storyCategory_en"].drop_duplicates().reset_index(drop=True)
            )
            df["story_category_id"] = df.join(
                story_categories.set_index("storyCategory_en"),
                on="storyCategory_en",
                how="left",
            )["story_category_id"]
        else:
            return None, None

        return story_categories, df

    def remove_unneeded_cols(self, df, required_cols: list):
        """Remove unneeded columns from the DataFrame.
        Args:
            df (pd.DataFrame): The DataFrame containing the news articles.
            required_cols (list): A list of columns to keep in the DataFrame.
        Returns:
            pd.DataFrame: The DataFrame with only the required columns.
        """
        if not required_cols:
            required_cols = self.default_cols
        return df[required_cols]
