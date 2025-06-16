# USPTO Data Cleaner

A Python-based toolkit for processing, cleaning, and structuring U.S. patent assignment data. This script transforms raw XML bulk data from the USPTO into cleaned, analyzable CSV files by merging it with patent classification and corporate ownership information.

## Overview

The US Patent and Trademark Office (USPTO) provides bulk data on patent assignments, but it requires significant processing to be useful for research and analysis. This project automates the entire data construction pipeline, from parsing the initial XML files to generating aggregated, analysis-ready datasets.

The main features of this script include:

- Parsing complex, nested XML assignment data.
- Cleaning and standardizing assignee and assignor information.
- Merging patent records with CPC and USPC classification data.
- Identifying corporate assignees and linking them to GVKEY identifiers.
- Flagging "green" patents based on OECD classifications.
- Aggregating patent counts by company and year.

## Important Notes

- **Performance**: Parsing large XML files is a computationally intensive and time-consuming process. Runtimes can be significant, especially when processing multiple years of data. Please be patient while the script executes the initial file processing steps.
- **Data Access**: The UVA Darden Patent Dataset (`GCPD_granular_data.txt`) is required for matching assignees to corporate identifiers (GVKEYs). This dataset is proprietary and must be requested separately. See the Data Sources section for details on how to apply for access.

## Data Sources

This pipeline relies on several external data sources that must be downloaded first:

1. USPTO Patent Assignment Bulk Data

   : The primary raw data containing all assignment records.

   - **Source**: [USPTO Bulk Data](https://bulkdata.uspto.gov/data/patent/assignment/)
   - **Action**: Download the desired yearly or weekly XML files.

2. PatentsView Classification Data

   : Used to merge patent records with their corresponding CPC and USPC classifications.

   - **Source**: [PatentsView Data Download Tables](https://patentsview.org/download/data-download-tables)
   - **Required Files**: `g_cpc_current.tsv` and `g_uspc_at_issue.tsv`.

3. UVA Darden Patent Dataset

   : Provides matching between assignee names and corporate GVKEYs.

   - **Source**: [Darden School of Business at the University of Virginia](https://patents.darden.virginia.edu/)
   - **Action**: This data is not publicly available and requires users to apply for access directly via the Darden website.
   - **Required File**: `GCPD_granular_data.txt`.

4. OECD Green Technology Classification

   : A list of CPC groups corresponding to environmentally-friendly technologies, note that the list should be manually copy as an excel file. I've add it into the subdirectory for convenience.

   - **Source**: [OECD Environmental Innovation Data](https://www.oecd-ilibrary.org/environment/measuring-environmental-innovation-using-patent-data_5js009kf48xw-en)
   - **Required File**: `OECD_ENV_Tech_Patent_Group.csv`.

## Prerequisites

- Python 3.8+

```
pandas
numpy
xmltodict
tqdm
```

## Setup and Usage

### 1. Directory Structure

Before running the script, organize your files into the following directory structure:

```
.
├── uspto_data_cleaning.py      # The main Python script
└── data/
    ├── uspatent/
    │   ├── ad20230105.xml      # Example raw XML from USPTO
    │   ├── ...                 # Other XML files
    │   ├── g_cpc_current.tsv
    │   ├── g_uspc_at_issue.tsv
    │   └── OECD_ENV_Tech_Patent_Group.csv
    │
    ├── uva_darden/
    │   └── GCPD_granular_data.txt
    │
    └── results/         # Output directory (will be created automatically)
```

### 2. Running the Script

Execute the main script from your terminal or Python IDE. The script is encapsulated in a class, `PatentDataCleaner`.

The script allows for specifying a date range for the final analysis. You can modify the parameters in the `if __name__ == '__main__':` block of the script:

```python
# Example of running with a custom date range
cleaner_custom = PatentDataCleaner(
    base_path='./data',
    start_date_str='2010-01-01',
    end_date_str='2020-12-31'
)
cleaner_custom.run_pipeline()
```

## Data Processing Workflow

The script follows a multi-step procedure to process the data:

1. **XML Data Extraction**: Loads all `.xml` files from the `data/uspatent` directory, parses them, and extracts key assignment record fields into a Pandas DataFrame.
2. **Record Unnesting**: Processes the nested record structure to flatten details about assignors, assignees, and individual patent documents.
3. **Data Cleaning**: Filters out non-informative records, standardizes assignee and assignor names to lowercase, and normalizes spacing to prepare for merging.
4. **Classification Merging**: Merges the cleaned assignment data with CPC and USPC classification data based on the patent number.
5. **Corporate Identifier Assignment**: Links assignees to corporate `GVKEY` identifiers by matching names with the UVA Darden dataset.
6. **Final Processing & Aggregation**: Converts dates, flags green patents, and generates two final output files: a detailed corporate patent list and a yearly aggregated summary.

## Output Files and Schema

The pipeline generates three primary CSV files in the `data/results/` directory.

### `patent_assignment_with_class.csv`

This intermediate file contains cleaned and classified patent assignment data linked to corporate identifiers.

| Variable           | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `reel_no`          | Reel number for the USPTO record.                            |
| `frame_no`         | Frame number, used with reel_no to locate the record.        |
| `last_update_date` | Date when the record was last updated in the USPTO system.   |
| `recorded_date`    | Date when the transaction was officially recorded by the USPTO. |
| `patent_assignors` | Names of the original owners or parties transferring the patent rights. |
| `patent_assignees` | Names of the individuals or entities receiving the patent rights. |
| `patent_doc_num`   | Unique document number for the patent or patent application. |
| `patent_doc_kind`  | Type or kind of patent document, such as application or grant. |
| `cpc_group`        | Classification group in the Cooperative Patent Classification system. |
| `uspc_subclass_id` | Subclass identifier in the U.S. Patent Classification system. |
| `assg_name`        | Name of the entity or person receiving the patent rights.    |
| `gvkey`            | Unique global company identifier (GVKEY) for the assignee.   |

### `patent_corporate.csv`

A detailed, cleaned dataset of patent assignments for corporate entities.

| Variable            | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `patent_id`         | Unique identifier for the patent or patent application.      |
| `patent_kind`       | Type or kind of patent document.                             |
| `assignee_name`     | Name of the entity or person who holds the patent rights.    |
| `assignee_gvkey`    | Unique global company identifier (GVKEY) for the assignee.   |
| `date_recorded`     | Date when the transaction was recorded by the USPTO.         |
| `date_last_update`  | Date when the record was last updated in the USPTO system.   |
| `patent_cpc_group`  | Classification group in the Cooperative Patent Classification system. |
| `patent_uspc_group` | Classification group in the U.S. Patent Classification system. |
| `patent_is_green`   | Indicator (1 or 0) if the patent is related to "green" technologies. |

### `patent_aggregate.csv`

A summary file with patent counts aggregated by company and year.

| Variable             | Description                                                  |
| -------------------- | ------------------------------------------------------------ |
| `assignee_gvkey`     | Unique global company identifier (GVKEY) for the assignee.   |
| `assignee_name`      | Name of the assignee.                                        |
| `year_last_update`   | The year in which the record was last updated.               |
| `patent_num`         | The total number of patents assigned to this assignee in this year. |
| `patent_green_num`   | The number of green patents assigned to this assignee in this year. |
| `patent_green_total` | The ratio of green patents to total patents for the assignee in this year. |

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.