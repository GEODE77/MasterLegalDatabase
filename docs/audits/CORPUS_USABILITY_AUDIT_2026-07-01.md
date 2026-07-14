# Corpus Usability Audit

Generated: 2026-07-07T23:43:44.849296+00:00

This audit checks whether records can be identified and retrieved when requested.

- Index records checked: 57,155
- Records in retrieval catalog: 57,155
- Crosswalk rows checked: 9,980
- JSONL files checked: 209
- JSONL rows checked: 613,451
- JSONL rows with primary identifiers: 613,451
- Errors: 0
- Warnings: 0
- Ready for request identification: True
- Ready for basic use: True

## Layer Summary

| Layer | Records | Retrievable | Identity Complete | Source Anchored | Content Anchored | Errors | Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01_Statutes_CRS | 34,717 | 34,717 | 34,717 | 34,717 | 34,717 | 0 | 0 |
| 02_Regulations_CCR | 1,035 | 1,035 | 1,035 | 1,035 | 1,035 | 0 | 0 |
| 03_Legislation | 12,453 | 12,453 | 12,453 | 12,453 | 12,453 | 0 | 0 |
| 04_Rulemaking | 7,955 | 7,955 | 7,955 | 7,955 | 7,955 | 0 | 0 |
| 05_Executive_Orders | 535 | 535 | 535 | 535 | 535 | 0 | 0 |
| 06_Session_Laws | 437 | 437 | 437 | 437 | 437 | 0 | 0 |
| 07_Supplementary | 23 | 23 | 23 | 23 | 23 | 0 | 0 |

## Crosswalk Summary

| File | Rows | Endpoints Present | Labels Present | Evidence Present | Errors | Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regulation_to_statute.jsonl | 696 | 696 | 696 | 696 | 0 | 0 |
| statute_to_regulation.jsonl | 619 | 619 | 619 | 619 | 0 | 0 |
| bill_to_statute.jsonl | 7 | 7 | 7 | 7 | 0 | 0 |
| rulemaking_to_regulation.jsonl | 7,955 | 7,955 | 7,955 | 7,955 | 0 | 0 |
| agency_to_statute.jsonl | 696 | 696 | 696 | 696 | 0 | 0 |
| amendment_history.jsonl | 7 | 7 | 7 | 7 | 0 | 0 |

## JSONL Addressability

Every valid JSONL row is addressable by file and line number. Rows with a primary ID are also directly addressable by that ID.

| File | Rows | Primary IDs | File-Line Addressable | Invalid Rows |
| --- | ---: | ---: | ---: | ---: |
| 01_Statutes_CRS/_index.jsonl | 34,717 | 34,717 | 34,717 | 0 |
| 01_Statutes_CRS/_meta/crs_subject_index.jsonl | 129,054 | 129,054 | 129,054 | 0 |
| 01_Statutes_CRS/_meta/crs_title_01_meta.jsonl | 876 | 876 | 876 | 0 |
| 01_Statutes_CRS/_meta/crs_title_02_meta.jsonl | 319 | 319 | 319 | 0 |
| 01_Statutes_CRS/_meta/crs_title_03_meta.jsonl | 44 | 44 | 44 | 0 |
| 01_Statutes_CRS/_meta/crs_title_04_meta.jsonl | 673 | 673 | 673 | 0 |
| 01_Statutes_CRS/_meta/crs_title_05_meta.jsonl | 410 | 410 | 410 | 0 |
| 01_Statutes_CRS/_meta/crs_title_06_meta.jsonl | 451 | 451 | 451 | 0 |
| 01_Statutes_CRS/_meta/crs_title_07_meta.jsonl | 1,175 | 1,175 | 1,175 | 0 |
| 01_Statutes_CRS/_meta/crs_title_08_meta.jsonl | 1,049 | 1,049 | 1,049 | 0 |
| 01_Statutes_CRS/_meta/crs_title_09_meta.jsonl | 107 | 107 | 107 | 0 |
| 01_Statutes_CRS/_meta/crs_title_10_meta.jsonl | 1,355 | 1,355 | 1,355 | 0 |
| 01_Statutes_CRS/_meta/crs_title_11_meta.jsonl | 731 | 731 | 731 | 0 |
| 01_Statutes_CRS/_meta/crs_title_12_meta.jsonl | 1,262 | 1,262 | 1,262 | 0 |
| 01_Statutes_CRS/_meta/crs_title_13_meta.jsonl | 1,257 | 1,257 | 1,257 | 0 |
| 01_Statutes_CRS/_meta/crs_title_14_meta.jsonl | 339 | 339 | 339 | 0 |
| 01_Statutes_CRS/_meta/crs_title_15_meta.jsonl | 1,107 | 1,107 | 1,107 | 0 |
| 01_Statutes_CRS/_meta/crs_title_16_meta.jsonl | 605 | 605 | 605 | 0 |
| 01_Statutes_CRS/_meta/crs_title_17_meta.jsonl | 413 | 413 | 413 | 0 |
| 01_Statutes_CRS/_meta/crs_title_18_meta.jsonl | 958 | 958 | 958 | 0 |
| 01_Statutes_CRS/_meta/crs_title_19_meta.jsonl | 516 | 516 | 516 | 0 |
| 01_Statutes_CRS/_meta/crs_title_20_meta.jsonl | 34 | 34 | 34 | 0 |
| 01_Statutes_CRS/_meta/crs_title_21_meta.jsonl | 17 | 17 | 17 | 0 |
| 01_Statutes_CRS/_meta/crs_title_22_meta.jsonl | 1,364 | 1,364 | 1,364 | 0 |
| 01_Statutes_CRS/_meta/crs_title_23_meta.jsonl | 1,125 | 1,125 | 1,125 | 0 |
| 01_Statutes_CRS/_meta/crs_title_24_meta.jsonl | 3,464 | 3,464 | 3,464 | 0 |
| 01_Statutes_CRS/_meta/crs_title_25_5_meta.jsonl | 520 | 520 | 520 | 0 |
| 01_Statutes_CRS/_meta/crs_title_25_meta.jsonl | 1,725 | 1,725 | 1,725 | 0 |
| 01_Statutes_CRS/_meta/crs_title_26_5_meta.jsonl | 178 | 178 | 178 | 0 |
| 01_Statutes_CRS/_meta/crs_title_26_meta.jsonl | 514 | 514 | 514 | 0 |
| 01_Statutes_CRS/_meta/crs_title_27_meta.jsonl | 373 | 373 | 373 | 0 |
| 01_Statutes_CRS/_meta/crs_title_28_meta.jsonl | 278 | 278 | 278 | 0 |
| 01_Statutes_CRS/_meta/crs_title_29_meta.jsonl | 653 | 653 | 653 | 0 |
| 01_Statutes_CRS/_meta/crs_title_30_meta.jsonl | 833 | 833 | 833 | 0 |
| 01_Statutes_CRS/_meta/crs_title_31_meta.jsonl | 1,088 | 1,088 | 1,088 | 0 |
| 01_Statutes_CRS/_meta/crs_title_32_meta.jsonl | 907 | 907 | 907 | 0 |
| 01_Statutes_CRS/_meta/crs_title_33_meta.jsonl | 370 | 370 | 370 | 0 |
| 01_Statutes_CRS/_meta/crs_title_34_meta.jsonl | 328 | 328 | 328 | 0 |
| 01_Statutes_CRS/_meta/crs_title_35_meta.jsonl | 1,109 | 1,109 | 1,109 | 0 |
| 01_Statutes_CRS/_meta/crs_title_36_meta.jsonl | 174 | 174 | 174 | 0 |
| 01_Statutes_CRS/_meta/crs_title_37_meta.jsonl | 1,227 | 1,227 | 1,227 | 0 |
| 01_Statutes_CRS/_meta/crs_title_38_meta.jsonl | 1,199 | 1,199 | 1,199 | 0 |
| 01_Statutes_CRS/_meta/crs_title_39_meta.jsonl | 1,123 | 1,123 | 1,123 | 0 |
| 01_Statutes_CRS/_meta/crs_title_40_meta.jsonl | 582 | 582 | 582 | 0 |
| 01_Statutes_CRS/_meta/crs_title_41_meta.jsonl | 46 | 46 | 46 | 0 |
| 01_Statutes_CRS/_meta/crs_title_42_meta.jsonl | 833 | 833 | 833 | 0 |
| 01_Statutes_CRS/_meta/crs_title_43_meta.jsonl | 479 | 479 | 479 | 0 |
| 01_Statutes_CRS/_meta/crs_title_44_meta.jsonl | 527 | 527 | 527 | 0 |
| 02_Regulations_CCR/_dataset/ccr_items.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 02_Regulations_CCR/_dataset/ccr_items_tagged.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 02_Regulations_CCR/_dataset/environmental.jsonl | 100 | 100 | 100 | 0 |
| 02_Regulations_CCR/_dataset/labor_employment.jsonl | 53 | 53 | 53 | 0 |
| 02_Regulations_CCR/_dataset/manufacturing.jsonl | 272 | 272 | 272 | 0 |
| 02_Regulations_CCR/_dataset/validation_manufacturing.jsonl | 272 | 272 | 272 | 0 |
| 02_Regulations_CCR/_index.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 02_Regulations_CCR/_inventory/ccr_inventory_manifest.jsonl | 2,070 | 2,070 | 2,070 | 0 |
| 02_Regulations_CCR/_meta/ccr_normalized_meta.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 02_Regulations_CCR/_meta/ccr_rules_meta.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 02_Regulations_CCR/_meta/rule_units.jsonl | 13,059 | 13,059 | 13,059 | 0 |
| 02_Regulations_CCR/_meta/rule_units_quality.jsonl | 13,059 | 13,059 | 13,059 | 0 |
| 02_Regulations_CCR/_meta/rule_units_review_packets.jsonl | 532 | 532 | 532 | 0 |
| 02_Regulations_CCR/_meta/rule_units_review_queue.jsonl | 532 | 532 | 532 | 0 |
| 02_Regulations_CCR/_normalized/ccr_normalized_records.jsonl | 1,035 | 1,035 | 1,035 | 0 |
| 03_Legislation/2010/bills_2010.jsonl | 784 | 784 | 784 | 0 |
| 03_Legislation/2011/bills_2011.jsonl | 710 | 710 | 710 | 0 |
| 03_Legislation/2012/bills_2012.jsonl | 645 | 645 | 645 | 0 |
| 03_Legislation/2013/bills_2013.jsonl | 734 | 734 | 734 | 0 |
| 03_Legislation/2014/bills_2014.jsonl | 710 | 710 | 710 | 0 |
| 03_Legislation/2015/bills_2015.jsonl | 762 | 762 | 762 | 0 |
| 03_Legislation/2016/bills_2016.jsonl | 788 | 788 | 788 | 0 |
| 03_Legislation/2017/bills_2017.jsonl | 769 | 769 | 769 | 0 |
| 03_Legislation/2018/bills_2018.jsonl | 784 | 784 | 784 | 0 |
| 03_Legislation/2019/bills_2019.jsonl | 654 | 654 | 654 | 0 |
| 03_Legislation/2020/bills_2020.jsonl | 748 | 748 | 748 | 0 |
| 03_Legislation/2021/bills_2021.jsonl | 678 | 678 | 678 | 0 |
| 03_Legislation/2022/bills_2022.jsonl | 717 | 717 | 717 | 0 |
| 03_Legislation/2023/bills_2023.jsonl | 696 | 696 | 696 | 0 |
| 03_Legislation/2024/bills_2024.jsonl | 792 | 792 | 792 | 0 |
| 03_Legislation/2025/bills_2025.jsonl | 768 | 768 | 768 | 0 |
| 03_Legislation/2026/bills_2026.jsonl | 714 | 714 | 714 | 0 |
| 03_Legislation/_dataset/bills.jsonl | 12,453 | 12,453 | 12,453 | 0 |
| 03_Legislation/_documents/bill_documents.jsonl | 85,848 | 85,848 | 85,848 | 0 |
| 03_Legislation/_documents/safe_bulk_batches.jsonl | 117 | 117 | 117 | 0 |
| 03_Legislation/_index.jsonl | 12,453 | 12,453 | 12,453 | 0 |
| 03_Legislation/_meta/bills_meta.jsonl | 12,453 | 12,453 | 12,453 | 0 |
| 04_Rulemaking/2006/register_2006_Q3.jsonl | 31 | 31 | 31 | 0 |
| 04_Rulemaking/2006/register_2006_Q4.jsonl | 90 | 90 | 90 | 0 |
| 04_Rulemaking/2007/register_2007_Q1.jsonl | 94 | 94 | 94 | 0 |
| 04_Rulemaking/2007/register_2007_Q2.jsonl | 74 | 74 | 74 | 0 |
| 04_Rulemaking/2007/register_2007_Q3.jsonl | 103 | 103 | 103 | 0 |
| 04_Rulemaking/2007/register_2007_Q4.jsonl | 105 | 105 | 105 | 0 |
| 04_Rulemaking/2008/register_2008_Q1.jsonl | 80 | 80 | 80 | 0 |
| 04_Rulemaking/2008/register_2008_Q2.jsonl | 83 | 83 | 83 | 0 |
| 04_Rulemaking/2008/register_2008_Q3.jsonl | 98 | 98 | 98 | 0 |
| 04_Rulemaking/2008/register_2008_Q4.jsonl | 120 | 120 | 120 | 0 |
| 04_Rulemaking/2009/register_2009_Q1.jsonl | 94 | 94 | 94 | 0 |
| 04_Rulemaking/2009/register_2009_Q2.jsonl | 83 | 83 | 83 | 0 |
| 04_Rulemaking/2009/register_2009_Q3.jsonl | 91 | 91 | 91 | 0 |
| 04_Rulemaking/2009/register_2009_Q4.jsonl | 99 | 99 | 99 | 0 |
| 04_Rulemaking/2010/register_2010_Q1.jsonl | 87 | 87 | 87 | 0 |
| 04_Rulemaking/2010/register_2010_Q2.jsonl | 80 | 80 | 80 | 0 |
| 04_Rulemaking/2010/register_2010_Q3.jsonl | 157 | 157 | 157 | 0 |
| 04_Rulemaking/2010/register_2010_Q4.jsonl | 102 | 102 | 102 | 0 |
| 04_Rulemaking/2011/register_2011_Q1.jsonl | 91 | 91 | 91 | 0 |
| 04_Rulemaking/2011/register_2011_Q2.jsonl | 56 | 56 | 56 | 0 |
| 04_Rulemaking/2011/register_2011_Q3.jsonl | 77 | 77 | 77 | 0 |
| 04_Rulemaking/2011/register_2011_Q4.jsonl | 88 | 88 | 88 | 0 |
| 04_Rulemaking/2012/register_2012_Q1.jsonl | 83 | 83 | 83 | 0 |
| 04_Rulemaking/2012/register_2012_Q2.jsonl | 86 | 86 | 86 | 0 |
| 04_Rulemaking/2012/register_2012_Q3.jsonl | 83 | 83 | 83 | 0 |
| 04_Rulemaking/2012/register_2012_Q4.jsonl | 95 | 95 | 95 | 0 |
| 04_Rulemaking/2013/register_2013_Q1.jsonl | 86 | 86 | 86 | 0 |
| 04_Rulemaking/2013/register_2013_Q2.jsonl | 91 | 91 | 91 | 0 |
| 04_Rulemaking/2013/register_2013_Q3.jsonl | 95 | 95 | 95 | 0 |
| 04_Rulemaking/2013/register_2013_Q4.jsonl | 103 | 103 | 103 | 0 |
| 04_Rulemaking/2014/register_2014_Q1.jsonl | 87 | 87 | 87 | 0 |
| 04_Rulemaking/2014/register_2014_Q2.jsonl | 101 | 101 | 101 | 0 |
| 04_Rulemaking/2014/register_2014_Q3.jsonl | 110 | 110 | 110 | 0 |
| 04_Rulemaking/2014/register_2014_Q4.jsonl | 99 | 99 | 99 | 0 |
| 04_Rulemaking/2015/register_2015_Q1.jsonl | 94 | 94 | 94 | 0 |
| 04_Rulemaking/2015/register_2015_Q2.jsonl | 72 | 72 | 72 | 0 |
| 04_Rulemaking/2015/register_2015_Q3.jsonl | 80 | 80 | 80 | 0 |
| 04_Rulemaking/2015/register_2015_Q4.jsonl | 100 | 100 | 100 | 0 |
| 04_Rulemaking/2016/register_2016_Q1.jsonl | 99 | 99 | 99 | 0 |
| 04_Rulemaking/2016/register_2016_Q2.jsonl | 83 | 83 | 83 | 0 |
| 04_Rulemaking/2016/register_2016_Q3.jsonl | 68 | 68 | 68 | 0 |
| 04_Rulemaking/2016/register_2016_Q4.jsonl | 111 | 111 | 111 | 0 |
| 04_Rulemaking/2017/register_2017_Q1.jsonl | 94 | 94 | 94 | 0 |
| 04_Rulemaking/2017/register_2017_Q2.jsonl | 77 | 77 | 77 | 0 |
| 04_Rulemaking/2017/register_2017_Q3.jsonl | 70 | 70 | 70 | 0 |
| 04_Rulemaking/2017/register_2017_Q4.jsonl | 108 | 108 | 108 | 0 |
| 04_Rulemaking/2018/register_2018_Q1.jsonl | 84 | 84 | 84 | 0 |
| 04_Rulemaking/2018/register_2018_Q2.jsonl | 91 | 91 | 91 | 0 |
| 04_Rulemaking/2018/register_2018_Q3.jsonl | 71 | 71 | 71 | 0 |
| 04_Rulemaking/2018/register_2018_Q4.jsonl | 135 | 135 | 135 | 0 |
| 04_Rulemaking/2019/register_2019_Q1.jsonl | 117 | 117 | 117 | 0 |
| 04_Rulemaking/2019/register_2019_Q2.jsonl | 75 | 75 | 75 | 0 |
| 04_Rulemaking/2019/register_2019_Q3.jsonl | 86 | 86 | 86 | 0 |
| 04_Rulemaking/2019/register_2019_Q4.jsonl | 121 | 121 | 121 | 0 |
| 04_Rulemaking/2020/register_2020_Q1.jsonl | 110 | 110 | 110 | 0 |
| 04_Rulemaking/2020/register_2020_Q2.jsonl | 190 | 190 | 190 | 0 |
| 04_Rulemaking/2020/register_2020_Q3.jsonl | 122 | 122 | 122 | 0 |
| 04_Rulemaking/2020/register_2020_Q4.jsonl | 170 | 170 | 170 | 0 |
| 04_Rulemaking/2021/register_2021_Q1.jsonl | 116 | 116 | 116 | 0 |
| 04_Rulemaking/2021/register_2021_Q2.jsonl | 135 | 135 | 135 | 0 |
| 04_Rulemaking/2021/register_2021_Q3.jsonl | 102 | 102 | 102 | 0 |
| 04_Rulemaking/2021/register_2021_Q4.jsonl | 151 | 151 | 151 | 0 |
| 04_Rulemaking/2022/register_2022_Q1.jsonl | 106 | 106 | 106 | 0 |
| 04_Rulemaking/2022/register_2022_Q2.jsonl | 99 | 99 | 99 | 0 |
| 04_Rulemaking/2022/register_2022_Q3.jsonl | 119 | 119 | 119 | 0 |
| 04_Rulemaking/2022/register_2022_Q4.jsonl | 189 | 189 | 189 | 0 |
| 04_Rulemaking/2023/register_2023_Q1.jsonl | 104 | 104 | 104 | 0 |
| 04_Rulemaking/2023/register_2023_Q2.jsonl | 111 | 111 | 111 | 0 |
| 04_Rulemaking/2023/register_2023_Q3.jsonl | 80 | 80 | 80 | 0 |
| 04_Rulemaking/2023/register_2023_Q4.jsonl | 143 | 143 | 143 | 0 |
| 04_Rulemaking/2024/register_2024_Q1.jsonl | 99 | 99 | 99 | 0 |
| 04_Rulemaking/2024/register_2024_Q2.jsonl | 84 | 84 | 84 | 0 |
| 04_Rulemaking/2024/register_2024_Q3.jsonl | 78 | 78 | 78 | 0 |
| 04_Rulemaking/2024/register_2024_Q4.jsonl | 132 | 132 | 132 | 0 |
| 04_Rulemaking/2025/register_2025_Q1.jsonl | 88 | 88 | 88 | 0 |
| 04_Rulemaking/2025/register_2025_Q2.jsonl | 88 | 88 | 88 | 0 |
| 04_Rulemaking/2025/register_2025_Q3.jsonl | 96 | 96 | 96 | 0 |
| 04_Rulemaking/2025/register_2025_Q4.jsonl | 131 | 131 | 131 | 0 |
| 04_Rulemaking/2026/register_2026_Q1.jsonl | 80 | 80 | 80 | 0 |
| 04_Rulemaking/2026/register_2026_Q2.jsonl | 94 | 94 | 94 | 0 |
| 04_Rulemaking/_dataset/edocket_details.jsonl | 315 | 315 | 315 | 0 |
| 04_Rulemaking/_dataset/edocket_documents.jsonl | 516 | 516 | 516 | 0 |
| 04_Rulemaking/_dataset/rulemaking_notices.jsonl | 7,955 | 7,955 | 7,955 | 0 |
| 04_Rulemaking/_index.jsonl | 7,955 | 7,955 | 7,955 | 0 |
| 04_Rulemaking/_meta/rulemaking_notices_meta.jsonl | 7,955 | 7,955 | 7,955 | 0 |
| 04_Rulemaking/_quality/register_extraction_gaps.jsonl | 0 | 0 | 0 | 0 |
| 04_Rulemaking/_quality/register_extraction_quarantine.jsonl | 0 | 0 | 0 | 0 |
| 04_Rulemaking/_quality/review_sample_high_confidence.jsonl | 25 | 25 | 25 | 0 |
| 04_Rulemaking/_quality/review_sample_low_confidence.jsonl | 0 | 0 | 0 | 0 |
| 04_Rulemaking/_quality/review_sample_quarantine.jsonl | 0 | 0 | 0 | 0 |
| 05_Executive_Orders/2010_2019/exec_orders_2010_2019.jsonl | 18 | 18 | 18 | 0 |
| 05_Executive_Orders/2020_2029/exec_orders_2020_2029.jsonl | 517 | 517 | 517 | 0 |
| 05_Executive_Orders/_index.jsonl | 535 | 535 | 535 | 0 |
| 06_Session_Laws/2026/session_laws_2026.jsonl | 437 | 437 | 437 | 0 |
| 06_Session_Laws/_index.jsonl | 437 | 437 | 437 | 0 |
| 06_Session_Laws/_meta/session_laws_meta.jsonl | 437 | 437 | 437 | 0 |
| 07_Supplementary/_index.jsonl | 23 | 23 | 23 | 0 |
| 07_Supplementary/_meta/ag_opinions_meta.jsonl | 6 | 6 | 6 | 0 |
| 07_Supplementary/_meta/coprrr_reviews_meta.jsonl | 17 | 17 | 17 | 0 |
| 07_Supplementary/ag_opinions/ag_opinions_2021.jsonl | 1 | 1 | 1 | 0 |
| 07_Supplementary/ag_opinions/ag_opinions_2023.jsonl | 3 | 3 | 3 | 0 |
| 07_Supplementary/ag_opinions/ag_opinions_2024.jsonl | 1 | 1 | 1 | 0 |
| 07_Supplementary/ag_opinions/ag_opinions_2026.jsonl | 1 | 1 | 1 | 0 |
| 07_Supplementary/coprrr_reviews/coprrr_reviews_2025.jsonl | 17 | 17 | 17 | 0 |
| _CONTROL_PLANE/CORPUS_USABILITY_ISSUES.jsonl | 0 | 0 | 0 | 0 |
| _CONTROL_PLANE/FULL_TEXT_DIFF.jsonl | 1,106 | 1,106 | 1,106 | 0 |
| _CONTROL_PLANE/GOLDEN_SAMPLE_REVIEW_SET.jsonl | 130 | 130 | 130 | 0 |
| _CONTROL_PLANE/MANUAL_SOURCE_INTAKE_LEDGER.jsonl | 1 | 1 | 1 | 0 |
| _CONTROL_PLANE/MASTER_TIMELINE_INDEX.jsonl | 266 | 266 | 266 | 0 |
| _CONTROL_PLANE/RELATIONSHIP_ACCURACY_AUDIT.jsonl | 9,980 | 9,980 | 9,980 | 0 |
| _CONTROL_PLANE/RELATIONSHIP_COVERAGE.jsonl | 9,958 | 9,958 | 9,958 | 0 |
| _CONTROL_PLANE/RELATIONSHIP_COVERAGE_SUMMARY.jsonl | 6 | 6 | 6 | 0 |
| _CONTROL_PLANE/RETRIEVAL_CATALOG.jsonl | 57,155 | 57,155 | 57,155 | 0 |
| _CONTROL_PLANE/SOURCE_STRENGTH_INDEX.jsonl | 57,154 | 57,154 | 57,154 | 0 |
| _CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl | 57,154 | 57,154 | 57,154 | 0 |
| _CONTROL_PLANE/UPDATE_LEDGER.jsonl | 2,619 | 2,619 | 2,619 | 0 |
| _CONTROL_PLANE/UPDATE_LOG.jsonl | 2,390 | 2,390 | 2,390 | 0 |
| _CROSSWALKS/agency_to_statute.jsonl | 696 | 696 | 696 | 0 |
| _CROSSWALKS/amendment_history.jsonl | 7 | 7 | 7 | 0 |
| _CROSSWALKS/bill_to_statute.jsonl | 7 | 7 | 7 | 0 |
| _CROSSWALKS/regulation_to_statute.jsonl | 696 | 696 | 696 | 0 |
| _CROSSWALKS/rulemaking_to_regulation.jsonl | 7,955 | 7,955 | 7,955 | 0 |
| _CROSSWALKS/statute_to_regulation.jsonl | 619 | 619 | 619 | 0 |
| _QUARANTINE/quarantine_log.jsonl | 2 | 2 | 2 | 0 |

## Files

- Machine report: `_CONTROL_PLANE/CORPUS_USABILITY_AUDIT.json`
- Issue rows: `_CONTROL_PLANE/CORPUS_USABILITY_ISSUES.jsonl`
- Repair queue: `_CONTROL_PLANE/CORPUS_USABILITY_REPAIR_QUEUE.json`

## Boundary

This audit checks local corpus usability: identifiers, source anchors, content anchors, retrieval visibility, and relationship row basics. It does not certify legal correctness or official-source freshness.
