import os
import re
import pandas as pd
import numpy as np
import xmltodict
from tqdm import tqdm


class PatentDataCleaner:

    def __init__(self, base_path='.', start_date_str='2002-01-01', end_date_str='2023-12-31'):
        self.uspatent_path = os.path.join(base_path, 'uspatent')
        self.other_data_path = os.path.join(base_path, 'uva_darden')
        self.output_path = os.path.join(base_path, 'results')
        os.makedirs(self.output_path, exist_ok=True)
        self.start_date = pd.to_datetime(start_date_str)
        self.end_date = pd.to_datetime(end_date_str)
        self.processed_data = None


    @staticmethod
    def _extract_record(xml_dict):
        records = []
        assignment_data = xml_dict.get('us-patent-assignments', {}).get('patent-assignments', {}).get('patent-assignment', [])
        if not isinstance(assignment_data, list):
            assignment_data = [assignment_data]

        for record in assignment_data:
            record_dict = {
                'reel-no': record.get('assignment-record', {}).get('reel-no'),
                'frame-no': record.get('assignment-record', {}).get('frame-no'),
                'last-update-date': record.get('assignment-record', {}).get('last-update-date', {}).get('date'),
                'purge-indicator': record.get('assignment-record', {}).get('purge-indicator'),
                'recorded-date': record.get('assignment-record', {}).get('recorded-date', {}).get('date'),
                'patent-assignors': [record.get('patent-assignors', {}).get('patent-assignor')],
                'patent-assignees': [record.get('patent-assignees', {}).get('patent-assignee')],
                'patent-properties': [record.get('patent-properties', {}).get('patent-property')]
            }
            df = pd.DataFrame.from_dict(record_dict)
            records.append(df)
        if not records:
            return pd.DataFrame()
        records = pd.concat(records).reset_index(drop=True)
        return records

    @staticmethod
    def _unnest_patent(records):
        patent_data = []
        for index, row in records.iterrows():
            base_info = {
                'reel_no': row['reel-no'],
                'frame_no': row['frame-no'],
                'last_update_date': row['last-update-date'],
                'recorded_date': row['recorded-date'],
                'purge_indicator': row['purge-indicator']
            }
            try:
                base_info['patent_assignors'] = [d['name'] for d in row['patent-assignors']]
            except (TypeError, KeyError):
                base_info['patent_assignors'] = [row['patent-assignors']['name']] if isinstance(row.get('patent-assignors'), dict) else np.nan

            try:
                base_info['patent_assignees'] = [d['name'] for d in row['patent-assignees']]
            except (TypeError, KeyError):
                base_info['patent_assignees'] = [row['patent-assignees']['name']] if isinstance(row.get('patent-assignees'), dict) else np.nan

            patent_documents = []
            properties = row.get('patent-properties', [])
            if not isinstance(properties, list):
                properties = [properties]

            for prop_item in properties:
                if not prop_item: continue
                doc_ids = prop_item.get('document-id', [])
                if not isinstance(doc_ids, list):
                    doc_ids = [doc_ids]
                for doc in doc_ids:
                    if isinstance(doc, dict):
                        patent_documents.append({
                            'doc_num': doc.get('doc-number'),
                            'doc_kind': doc.get('kind')
                        })

            for doc in patent_documents:
                full_record = base_info.copy()
                full_record['patent_documents'] = doc
                patent_data.append(full_record)

        if not patent_data:
            return pd.DataFrame()
        return pd.DataFrame(patent_data)

    def process_xml_files(self):
        print("Starting XML file processing...")
        files = [f for f in os.listdir(self.uspatent_path) if f.endswith('.xml')]
        for file in tqdm(files, desc="Processing XMLs"):
            file_path = os.path.join(self.uspatent_path, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                xml = f.read()

            xml_dict = xmltodict.parse(xml)
            records = self._extract_record(xml_dict)
            if records.empty:
                continue

            patent = self._unnest_patent(records)
            if patent.empty:
                continue

            patent_df = pd.DataFrame(patent)
            patent_df['patent_doc_num'] = patent_df['patent_documents'].apply(lambda x: x.get('doc_num'))
            patent_df['patent_doc_kind'] = patent_df['patent_documents'].apply(lambda x: x.get('doc_kind'))
            patent_df = patent_df.loc[patent_df['patent_doc_kind'] != 'X0']
            patent_df = patent_df.drop('patent_documents', axis=1)
            patent_df = patent_df.loc[patent_df['patent_assignees'].notna()]

            patent_df['patent_assignors'] = patent_df['patent_assignors'].apply(lambda x: [name.lower() for name in x] if isinstance(x, list) else np.nan)
            patent_df['patent_assignees'] = patent_df['patent_assignees'].apply(lambda x: [name.lower() for name in x] if isinstance(x, list) else np.nan)
            patent_df = patent_df.explode('patent_assignees').dropna(subset=['patent_assignees'])

            patent_df['patent_assignees'] = patent_df['patent_assignees'].apply(lambda x: re.sub(r'\\', '', x))
            patent_df['patent_assignees'] = patent_df['patent_assignees'].apply(lambda x: re.sub(r'\s+', ' ', x))

            output_csv_path = os.path.join(self.uspatent_path, file[:-4] + '.csv')
            patent_df.to_csv(output_csv_path, index=False)

    def merge_with_classification(self):
        print("Merging with patent classification data...")
        cpc_class = pd.read_csv(os.path.join(self.uspatent_path, 'g_cpc_current.tsv'), sep='\t')
        uspc_class = pd.read_csv(os.path.join(self.uspatent_path, 'g_uspc_at_issue.tsv'), sep='\t')

        cpc_class = cpc_class[['patent_id', 'cpc_group']].drop_duplicates(subset=['patent_id'], keep='last')
        cpc_class['patent_id'] = cpc_class['patent_id'].astype(str)
        uspc_class = uspc_class[['patent_id', 'uspc_subclass_id']].drop_duplicates(subset=['patent_id'], keep='last')
        uspc_class['patent_id'] = uspc_class['patent_id'].astype(str)

        files = [f for f in os.listdir(self.uspatent_path) if f.endswith('.csv') and f.startswith('ad')]

        patent_with_class = []
        for file in tqdm(files, desc="Merging classification"):
            file_path = os.path.join(self.uspatent_path, file)
            patent = pd.read_csv(file_path)
            patent['patent_doc_num'] = patent['patent_doc_num'].astype(str)

            patent = patent.merge(cpc_class, how='left', left_on='patent_doc_num', right_on='patent_id').drop('patent_id', axis=1)
            patent = patent.merge(uspc_class, how='left', left_on='patent_doc_num', right_on='patent_id').drop('patent_id', axis=1)
            patent = patent.loc[(patent['cpc_group'].notna()) | (patent['uspc_subclass_id'].notna())]
            patent = patent.drop_duplicates()
            patent_with_class.append(patent)

        self.processed_data = pd.concat(patent_with_class, ignore_index=True)

    def merge_with_corporate_data(self):
        print("Merging with corporate data...")
        patent_name = pd.read_csv(os.path.join(self.other_data_path, 'GCPD_granular_data.txt'), sep=',')
        patent_name = patent_name[['assg_name', 'gvkey']].drop_duplicates()
        patent_name['assg_name'] = patent_name['assg_name'].str.lower().str.replace(r'[^\w\s]', ' ', regex=True)

        self.processed_data['patent_assignees'] = self.processed_data['patent_assignees'].astype(str).str.replace(r'[^\w\s]', ' ', regex=True)
        self.processed_data = self.processed_data.merge(patent_name, how='left', left_on='patent_assignees', right_on='assg_name')

        output_file = os.path.join(self.output_path, 'patent_assignment_with_class.csv')
        self.processed_data.to_csv(output_file, index=False)

    def finalize_and_aggregate(self):
        print("Finalizing and aggregating...")
        patent_corporate = self.processed_data.loc[self.processed_data['gvkey'].notna()].copy()
        patent_corporate['recorded_date'] = pd.to_datetime(patent_corporate['recorded_date'], format='%Y%m%d')
        patent_corporate['last_update_date'] = pd.to_datetime(patent_corporate['last_update_date'], format='%Y%m%d')

        patent_corporate = patent_corporate[['patent_doc_num', 'patent_doc_kind', 'patent_assignees', 'gvkey', 'recorded_date', 'last_update_date', 'cpc_group', 'uspc_subclass_id']]
        patent_corporate = patent_corporate.rename(columns={
            'patent_doc_num': 'patent_id', 'patent_doc_kind': 'patent_kind',
            'patent_assignees': 'assignee_name', 'gvkey': 'assignee_gvkey',
            'recorded_date': 'date_recorded', 'last_update_date': 'date_last_update',
            'cpc_group': 'patent_cpc_group', 'uspc_subclass_id': 'patent_uspc_group'
        })

        green_class_df = pd.read_csv(os.path.join(self.uspatent_path, 'OECD_ENV_Tech_Patent_Group.csv'))
        green_class = green_class_df['cpc_group'].tolist()
        patent_corporate['patent_is_green'] = np.where(patent_corporate['patent_cpc_group'].isin(green_class), 1, 0)

        df = patent_corporate.loc[
            (patent_corporate['date_recorded'] <= self.end_date) &
            (patent_corporate['date_recorded'] >= self.start_date)
            ].copy()
        print(f"Total records between {self.start_date.date()} and {self.end_date.date()}: {len(df)}")
        print(f"Total green records between {self.start_date.date()} and {self.end_date.date()}: {len(df.loc[df['patent_is_green'] == 1])}")

        df['year_recorded'] = df['date_recorded'].dt.year
        year_summary = pd.DataFrame()
        year_summary['total'] = df.groupby('year_recorded')['patent_id'].nunique()
        year_summary['green'] = df.loc[df['patent_is_green'] == 1].groupby('year_recorded')['patent_id'].nunique()

        output_corporate_file = os.path.join(self.output_path, 'patent_corporate.csv')
        df.to_csv(output_corporate_file, index=False)
        print(f"Corporate level patent data saved to {output_corporate_file}")

        patent_number = df.groupby(['assignee_gvkey', 'assignee_name', 'year_recorded']).agg(
            patent_num=('patent_id', 'size'),
            patent_green_num=('patent_is_green', 'sum')
        ).reset_index()
        patent_number = patent_number.rename(columns={'year_recorded': 'year'})
        patent_number['patent_green_total'] = patent_number['patent_green_num'] / patent_number['patent_num']

        output_agg_file = os.path.join(self.output_path, 'patent_aggregate.csv')
        patent_number.to_csv(output_agg_file, index=False)
        print(f"Aggregated patent data saved to {output_agg_file}")

    def run_pipeline(self):
        self.process_xml_files()
        self.merge_with_classification()
        self.merge_with_corporate_data()
        self.finalize_and_aggregate()



if __name__ == '__main__':
    # Usage example:
    # Assumes a directory structure like:
    # ./data/
    # ├── uspatent/
    # │   ├── ad19800101-20231231-01.xml
    # │   ├── ad19800101-20231231-02.xml
    # │   ├── g_cpc_current.tsv
    # │   ├── g_uspc_at_issue.tsv
    # │   └── OECD_ENV_Tech_Patent_Group.csv
    # ├── uva_darden/
    # │   └── GCPD_granular_data.txt
    # └── results/  (will be created)

    # --- To run with the default dates ('2002-01-01' to '2022-12-31') ---
    cleaner_default = PatentDataCleaner(base_path='./data')
    cleaner_default.run_pipeline()

    # --- Example of running with a custom date range and file paths---
    # cleaner_custom = PatentDataCleaner(
    #     base_path='./data',
    #     start_date_str='2010-01-01',
    #     end_date_str='2020-12-31'
    # )
    # cleaner_custom.run_pipeline()