"""Create the statewide Colorado county source coverage matrix."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any

from geode.utils.file_io import atomic_write_json, iter_jsonl
from geode.utils.file_io import load_json

COUNTY_NAMES = (
    "Adams", "Alamosa", "Arapahoe", "Archuleta", "Baca", "Bent", "Boulder",
    "Broomfield", "Chaffee", "Cheyenne", "Clear Creek", "Conejos", "Costilla",
    "Crowley", "Custer", "Delta", "Denver", "Dolores", "Douglas", "Eagle",
    "Elbert", "El Paso", "Fremont", "Garfield", "Gilpin", "Grand", "Gunnison",
    "Hinsdale", "Huerfano", "Jackson", "Jefferson", "Kiowa", "Kit Carson",
    "La Plata", "Lake", "Larimer", "Las Animas", "Lincoln", "Logan", "Mesa",
    "Mineral", "Moffat", "Montezuma", "Montrose", "Morgan", "Otero", "Ouray",
    "Park", "Phillips", "Pitkin", "Prowers", "Pueblo", "Rio Blanco", "Rio Grande",
    "Routt", "Saguache", "San Juan", "San Miguel", "Sedgwick", "Summit", "Teller",
    "Washington", "Weld", "Yuma",
)

SOURCE_CATEGORIES = (
    "county_ordinances",
    "county_codes",
    "land_use_zoning",
    "subdivision_development",
    "building_construction",
    "public_health",
    "environmental_open_burning",
    "roads_transportation_access",
    "animal_control_nuisance",
    "emergency_fire_restrictions",
    "continuing_resolutions",
    "administrative_rule_manuals",
    "archived_versions",
)

CATEGORY_TERM_MAP = {
    "county_ordinances": ("ordinance",),
    "county_codes": ("code",),
    "land_use_zoning": ("zoning", "landuse", "landdevelopment", "planning"),
    "subdivision_development": ("subdivision", "development"),
    "building_construction": ("building", "construction"),
    "public_health": ("publichealth", "health", "rodent", "rubbish", "garbage"),
    "environmental_open_burning": ("environment", "openburn", "burning", "stormwater"),
    "roads_transportation_access": ("road", "traffic", "transport", "access"),
    "animal_control_nuisance": ("animal", "nuisance", "dog", "weed"),
    "emergency_fire_restrictions": ("emergency", "fire", "wildfire", "restriction"),
    "continuing_resolutions": ("resolution",),
    "administrative_rule_manuals": ("regulation", "rule", "manual", "policy"),
}

COUNTY_HOME_URLS = {
    "Adams": "https://www.adcogov.org/",
    "Alamosa": "https://www.alamosacounty.org/",
    "Arapahoe": "https://www.arapahoeco.gov/",
    "Archuleta": "https://www.archuletacounty.org/",
    "Baca": "https://www.bacacountyco.gov/",
    "Bent": "https://www.bentcounty.net/index.php",
    "Boulder": "https://bouldercounty.gov/",
    "Broomfield": "https://www.broomfield.org/",
    "Chaffee": "https://www.chaffeecounty.org/",
    "Cheyenne": "https://www.co.cheyenne.co.us/",
    "Clear Creek": "https://www.clearcreekcounty.us/",
    "Conejos": "https://conejoscounty.colorado.gov/",
    "Costilla": "https://www.costillacounty.gov/",
    "Crowley": "https://crowleycounty.colorado.gov/",
    "Custer": "https://custercounty-co.gov/",
    "Delta": "https://www.deltacountyco.gov/",
    "Denver": "https://www.denvergov.org/",
    "Dolores": "https://dolocnty.colorado.gov/",
    "Douglas": "https://www.douglas.co.us/",
    "Eagle": "https://www.eaglecounty.us/",
    "Elbert": "https://co-elbertcounty.civicplus.com/",
    "El Paso": "https://clerkandrecorder.elpasoco.com/",
    "Fremont": "https://fremontcountyco.state.co.us/",
    "Garfield": "https://www.garfield-county.com/",
    "Gilpin": "https://gilpincounty.colorado.gov/",
    "Grand": "https://co.grand.co.us/",
    "Gunnison": "https://www.gunnisoncounty.org/",
    "Hinsdale": "https://hinsdalecounty.colorado.gov/",
    "Huerfano": "https://huerfano.us/",
    "Jackson": "https://jacksoncountyco.gov/",
    "Jefferson": "https://www.jeffco.us/",
    "Kiowa": "https://kiowacounty-colorado.com/",
    "Kit Carson": "https://kitcarsoncounty.colorado.gov/",
    "La Plata": "https://www.co.laplata.co.us/",
    "Lake": "https://www.lakecountyco.com/",
    "Larimer": "https://www.larimer.gov/",
    "Las Animas": "https://lasanimascounty.colorado.gov/",
    "Lincoln": "https://lincolncounty.colorado.gov/",
    "Logan": "https://logancountyco.gov/",
    "Mesa": "https://www.mesacounty.us/",
    "Mineral": "https://www.mineralcountycolorado.com/",
    "Moffat": "https://moffatcounty.colorado.gov/",
    "Montezuma": "https://montezumacounty.org/",
    "Montrose": "https://www.montrosecounty.net/",
    "Morgan": "https://morgancounty.colorado.gov/",
    "Otero": "https://oterocounty.colorado.gov/",
    "Ouray": "https://www.ouraycountyco.gov/",
    "Park": "https://www.parkco.us/",
    "Phillips": "https://phillipscounty.colorado.gov/",
    "Pitkin": "https://www.pitkincounty.com/",
    "Prowers": "https://www.prowersco.gov/",
    "Pueblo": "https://county.pueblo.org/",
    "Rio Blanco": "https://www.rbc.us/",
    "Rio Grande": "https://www.riograndecounty.org/",
    "Routt": "https://co.routt.co.us/",
    "Saguache": "https://www.saguachecounty.net/",
    "San Juan": "https://sanjuancounty.colorado.gov/",
    "San Miguel": "https://www.sanmiguelcountyco.gov/",
    "Sedgwick": "https://sedgwickcounty.colorado.gov/",
    "Summit": "https://www.summitcountyco.gov/",
    "Teller": "https://www.co.teller.co.us/",
    "Washington": "https://www.co.washington.co.us/",
    "Weld": "https://www.weld.gov/",
    "Yuma": "https://yumacounty.net/",
}

SEED_SOURCE_RECORDS = (
    {
        "source_id": "county_adams_land_use_chapter_2",
        "authority_id": "CO-COUNTY-ADAMS",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://adcogov.org/documents/development-standards-regulations-chapter-2",
    },
    {
        "source_id": "county_arapahoe_codes_criteria_ordinances",
        "authority_id": "CO-COUNTY-ARAPAHOE",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://files.arapahoeco.gov/your_county/codes_criteria_and_ordinances/index.php",
    },
    {
        "source_id": "county_arapahoe_land_development_code",
        "authority_id": "CO-COUNTY-ARAPAHOE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://files.arapahoeco.gov/Public%20Works_Development/zoning/Land%20Development%20Code/LandDevelopmentCodeRev12102024.pdf",
    },
    {
        "source_id": "county_douglas_zoning_resolution",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.douglas.co.us/documents/section-1.pdf/",
    },
    {
        "source_id": "county_jefferson_zoning_resolution",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.jeffco.us/2460/Zoning-Resolution",
    },
    {
        "source_id": "county_jefferson_land_use_planning",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.jeffco.us/303/Land-Use-Planning",
    },
    {
        "source_id": "county_jefferson_regulations",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.jeffco.us/322/Regulations",
    },
    {
        "source_id": "county_boulder_ordinances",
        "authority_id": "CO-COUNTY-BOULDER",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://bouldercounty.gov/government/ordinances/",
    },
    {
        "source_id": "county_boulder_land_use_code",
        "authority_id": "CO-COUNTY-BOULDER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://bouldercounty.gov/property-and-land/land-use/planning/land-use-code/",
    },
    {
        "source_id": "county_boulder_land_use_article_4",
        "authority_id": "CO-COUNTY-BOULDER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://assets.bouldercounty.gov/wp-content/uploads/2017/02/land-use-code-article-04.pdf",
    },
    {
        "source_id": "county_garfield_land_use_development_code",
        "authority_id": "CO-COUNTY-GARFIELD",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.garfield-county.com/community-development/filesgcco/sites/12/10-17-24-complete-land-use-and-development-code.pdf",
    },
    {
        "source_id": "county_pueblo_code",
        "authority_id": "CO-COUNTY-PUEBLO",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://county.pueblo.org/county-attorney-department/pueblo-county-code",
    },
    {
        "source_id": "county_pueblo_unified_development_code",
        "authority_id": "CO-COUNTY-PUEBLO",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://county.pueblo.org/sites/default/files/2024-10/PuebloCounty_UDC_Adopted10.22.24.pdf",
    },
    {
        "source_id": "county_pueblo_building_code",
        "authority_id": "CO-COUNTY-PUEBLO",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://county.pueblo.org/county-attorney-department/chapter-1501-building-division-administration-and-general-provisions",
    },
    {
        "source_id": "county_pueblo_open_fire_ordinance",
        "authority_id": "CO-COUNTY-PUEBLO",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://county.pueblo.org/book/export/html/584",
    },
    {
        "source_id": "county_pueblo_fire_code",
        "authority_id": "CO-COUNTY-PUEBLO",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://county.pueblo.org/book/export/html/360",
    },
    {
        "source_id": "county_adams_building_codes",
        "authority_id": "CO-COUNTY-ADAMS",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://epermits.adcogov.org/adopted-building-codes",
    },
    {
        "source_id": "county_adams_development_standards",
        "authority_id": "CO-COUNTY-ADAMS",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://animalshelter.adcogov.org/development-standards-regulations",
    },
    {
        "source_id": "county_arapahoe_building_division",
        "authority_id": "CO-COUNTY-ARAPAHOE",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://files.arapahoeco.gov/your_county/county_departments/public_works_and_development/divisions/building/index.php",
    },
    {
        "source_id": "county_arapahoe_parking_ordinance",
        "authority_id": "CO-COUNTY-ARAPAHOE",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://files.arapahoeco.gov/your_county/codes_criteria_and_ordinances/parking_regulations_for_county_roads_and_properties_.php",
    },
    {
        "source_id": "county_arapahoe_building_resolution",
        "authority_id": "CO-COUNTY-ARAPAHOE",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://files.arapahoeco.gov/Public%20Works_Development/Building/Resolution.2021.Building.I-Codes.FinaltoSet.pdf",
    },
    {
        "source_id": "county_jefferson_health_resolutions",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.jeffco.us/3719/Resolutions-and-Proclamations",
    },
    {
        "source_id": "county_jefferson_building_policy",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.jeffco.us/DocumentCenter/View/55983/2024-Regulatory-Building-Code-Policy-Draft--FINAL",
    },
    {
        "source_id": "county_jefferson_outside_home",
        "authority_id": "CO-COUNTY-JEFFERSON",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://www.jeffco.us/3975/Outside-the-Home/",
    },
    {
        "source_id": "county_douglas_building_resolution",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://publicnotices.douglas.co.us/resolutions/r-019-124-amending-the-douglas-county-building-code-through-adoption-of-the-following-revised-codes-the-2018-international-building-code-2018-international-building-code-appendix-c-2018-international-residential-code-2018-international-pluming-code-2018-international-plumbing-code-appendix-e-2018-international-mechanical-code-2018-international-fuel-gas-code-2018-international-energy-conservation-code-with-amendments/",
    },
    {
        "source_id": "county_alamosa_board_ordinances",
        "authority_id": "CO-COUNTY-ALAMOSA",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.alamosacounty.org/195/Board-of-County-Commissioners",
    },
    {
        "source_id": "county_alamosa_land_use_building",
        "authority_id": "CO-COUNTY-ALAMOSA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.alamosacounty.org/178/Land-Use-Building",
    },
    {
        "source_id": "county_archuleta_land_use_general",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.archuletacounty.org/DocumentCenter/View/3689/Section-1--General-Admin-Amend-2022-32",
    },
    {
        "source_id": "county_archuleta_zoning",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://archuletacounty.org/DocumentCenter/View/4507/Section-3---Zoning-Amend-2023-71",
    },
    {
        "source_id": "county_archuleta_quick_links",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.archuletacounty.org/QuickLinks.aspx",
    },
    {
        "source_id": "county_baca_open_burning",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.bacacountyco.gov/ordinance-no-7/",
    },
    {
        "source_id": "county_baca_zoning",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.bacacountyco.gov/government/county-commissioners/zoning-permits-and-land-use/",
    },
    {
        "source_id": "county_baca_fire_restrictions",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.bacacountyco.gov/",
    },
    {
        "source_id": "county_chaffee_land_use_code",
        "authority_id": "CO-COUNTY-CHAFFEE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://search.chaffeecounty.org/Planning-and-Zoning-Land-Use-Code",
    },
    {
        "source_id": "county_clear_creek_source_map",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.clearcreekcounty.us/SiteMap",
    },
    {
        "source_id": "county_custer_zoning_regulations",
        "authority_id": "CO-COUNTY-CUSTER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://custercounty-co.gov/departments/planning-zoning/zoning-regulations/",
    },
    {
        "source_id": "county_delta_land_use_regulations",
        "authority_id": "CO-COUNTY-DELTA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.deltacountyco.gov/680/Land-Use-Regulations",
    },
    {
        "source_id": "county_delta_building_land_use_subdivision",
        "authority_id": "CO-COUNTY-DELTA",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.deltacountyco.gov/730/BuildingLand-UseSubdivision",
    },
    {
        "source_id": "county_delta_2024_land_use_code",
        "authority_id": "CO-COUNTY-DELTA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.deltacountyco.gov/DocumentCenter/View/16005/2024-Delta-County-Land-Use-Code",
    },
    {
        "source_id": "county_conejos_construction_permit_instructions",
        "authority_id": "CO-COUNTY-CONEJOS",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://conejoscounty.colorado.gov/sites/conejoscounty/files/documents/ConstructionPermitStepbyStepInstructions11-2023_ADA.pdf",
    },
    {
        "source_id": "county_costilla_planning_zoning",
        "authority_id": "CO-COUNTY-COSTILLA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.costillacounty.gov/planning-and-zoning",
    },
    {
        "source_id": "county_costilla_planning_resources",
        "authority_id": "CO-COUNTY-COSTILLA",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.costillacounty.gov/planning-and-zoning/page/planning-zoning-resources",
    },
    {
        "source_id": "county_costilla_land_use_code",
        "authority_id": "CO-COUNTY-COSTILLA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.costillacounty.gov/media/2011",
    },
    {
        "source_id": "county_denver_regulations_codes_standards",
        "authority_id": "CO-COUNTY-DENVER",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.denvergov.org/My-Property/Remodeling-and-Construction/Permit-Office/Code",
    },
    {
        "source_id": "county_denver_zoning_code",
        "authority_id": "CO-COUNTY-DENVER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://denvergov.org/files/assets/public/community-planning-and-development/documents/zoning/denver-zoning-code/complete_denver_zoning_code.pdf",
    },
    {
        "source_id": "county_denver_archived_building_codes",
        "authority_id": "CO-COUNTY-DENVER",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.denvergov.org/files/assets/public/v/2/community-planning-and-development/documents/ds/building-codes/archive-codes/1976-1990_dbc.pdf",
    },
    {
        "source_id": "county_denver_zoning_administration_article_12",
        "authority_id": "CO-COUNTY-DENVER",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://denvergov.org/files/assets/public/community-planning-and-development/documents/zoning/denver-zoning-code/denver_zoning_code_article12_administration.pdf",
    },
    {
        "source_id": "county_eagle_land_use_regulations",
        "authority_id": "CO-COUNTY-EAGLE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://online.encodeplus.com/regs/eaglecounty-co/index.aspx",
    },
    {
        "source_id": "county_elbert_regulations",
        "authority_id": "CO-COUNTY-ELBERT",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.elbertcounty-co.gov/334/Regulations",
    },
    {
        "source_id": "county_elbert_recorded_ordinances_resolutions",
        "authority_id": "CO-COUNTY-ELBERT",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.elbertcounty-co.gov/307/Recorded-Ordinances-Resolutions",
    },
    {
        "source_id": "county_elbert_building_code_ordinance",
        "authority_id": "CO-COUNTY-ELBERT",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.elbertcounty-co.gov/DocumentCenter/View/1955/Ordinance-22-01-Amend-and-Restate-Ordinance-18-04-Adopting-International-Building-Code-2018-PDF",
    },
    {
        "source_id": "county_elpaso_ordinances",
        "authority_id": "CO-COUNTY-EL_PASO",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://clerkandrecorder.elpasoco.com/clerk-to-the-board/ordinances/",
    },
    {
        "source_id": "county_elpaso_land_development_code",
        "authority_id": "CO-COUNTY-EL_PASO",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://planningdevelopment.elpasoco.com/wp-content/uploads/LandUseCode/EPC-Land-Use-Code-Chapter-1-2016.pdf",
    },
    {
        "source_id": "county_elpaso_land_development_administration",
        "authority_id": "CO-COUNTY-EL_PASO",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://planningdevelopment.elpasoco.com/wp-content/uploads/LandUseCode/EPC-Land-Use-Code-Chapter-2-2016.pdf",
    },
    {
        "source_id": "county_elpaso_land_development_uses",
        "authority_id": "CO-COUNTY-EL_PASO",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://planningdevelopment.elpasoco.com/wp-content/uploads/LandUseCode/New-LDC-Chapter-5.pdf",
    },
    {
        "source_id": "county_fremont_zoning_resolution",
        "authority_id": "CO-COUNTY-FREMONT",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://fremontcountyco.gov/content/zoning-resolution",
    },
    {
        "source_id": "county_fremont_zoning_regulations_pdf",
        "authority_id": "CO-COUNTY-FREMONT",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://fremontcountyco.gov/sites/default/files/FC_Zoning_Regulations.pdf",
    },
    {
        "source_id": "county_fremont_commissioner_records",
        "authority_id": "CO-COUNTY-FREMONT",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.fremontcountyclerkco.gov/services/commissioner-records/",
    },
    {
        "source_id": "county_grand_planning_zoning",
        "authority_id": "CO-COUNTY-GRAND",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.co.grand.co.us/1122/Planning-Zoning",
    },
    {
        "source_id": "county_grand_building_development",
        "authority_id": "CO-COUNTY-GRAND",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.co.grand.co.us/644/5971/Building-and-Developing---in-the-County",
    },
    {
        "source_id": "county_grand_archived_regulations",
        "authority_id": "CO-COUNTY-GRAND",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.co.grand.co.us/Pages/ViewArchives/Index/1133",
    },
    {
        "source_id": "county_gunnison_land_use_resolution",
        "authority_id": "CO-COUNTY-GUNNISON",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.gunnisoncounty.org/378/Land-Use-Resolution",
    },
    {
        "source_id": "county_gunnison_land_use_energy_environment",
        "authority_id": "CO-COUNTY-GUNNISON",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.gunnisoncounty.org/846/Land-Use-Energy-Environment",
    },
    {
        "source_id": "county_gunnison_building_office",
        "authority_id": "CO-COUNTY-GUNNISON",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://gunnisoncounty.org/139/Building-Office",
    },
    {
        "source_id": "county_gunnison_community_development",
        "authority_id": "CO-COUNTY-GUNNISON",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.gunnisoncounty.org/144/Community-and-Economic-Development",
    },
    {
        "source_id": "county_huerfano_land_use_building",
        "authority_id": "CO-COUNTY-HUERFANO",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://huerfano.us/departments/land-use/",
    },
    {
        "source_id": "county_huerfano_proposed_land_use_code",
        "authority_id": "CO-COUNTY-HUERFANO",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://huerfano.us/wp-content/uploads/Proposed-Housing-Related-Changes-to-the-Huerfano-County-Land-Use-Code-Combined.pdf",
    },
    {
        "source_id": "county_huerfano_news_ordinances_fire",
        "authority_id": "CO-COUNTY-HUERFANO",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://huerfano.us/news/",
    },
    {
        "source_id": "county_kit_carson_land_use",
        "authority_id": "CO-COUNTY-KIT_CARSON",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://kitcarsoncounty.colorado.gov/departments/land-use",
    },
    {
        "source_id": "county_kit_carson_homepage_resolutions_fire",
        "authority_id": "CO-COUNTY-KIT_CARSON",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://kitcarsoncounty.colorado.gov/",
    },
    {
        "source_id": "county_kit_carson_solid_waste",
        "authority_id": "CO-COUNTY-KIT_CARSON",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://kitcarsoncounty.colorado.gov/departments/solid-waste",
    },
    {
        "source_id": "county_kit_carson_sheriff_policies",
        "authority_id": "CO-COUNTY-KIT_CARSON",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://kitcarsoncounty.colorado.gov/kcc-sheriff/policy-and-forms-page",
    },
    {
        "source_id": "county_jackson_comprehensive_plan",
        "authority_id": "CO-COUNTY-JACKSON",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://jacksoncountygov.com/DocumentCenter/View/5518/Jackson-County-Comprehensive-Plan-2055",
    },
    {
        "source_id": "county_kiowa_commissioners_resolutions",
        "authority_id": "CO-COUNTY-KIOWA",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://kiowacounty-colorado.com/kiowa_county_commissioners.htm",
    },
    {
        "source_id": "county_kiowa_resolutions_archive",
        "authority_id": "CO-COUNTY-KIOWA",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://kiowacounty-colorado.com/RESOLUTIONS/resolutions.htm",
    },
    {
        "source_id": "county_kiowa_building_code_resolution",
        "authority_id": "CO-COUNTY-KIOWA",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://kiowacounty-colorado.com/Resolution%202023-06.pdf",
    },
    {
        "source_id": "county_kiowa_comprehensive_plan",
        "authority_id": "CO-COUNTY-KIOWA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://kiowacounty-colorado.com/P%26Z%20COMPREHENSIVE%20PLAN%20%281%29.pdf",
    },
    {
        "source_id": "county_lake_land_development_code",
        "authority_id": "CO-COUNTY-LAKE",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.lakecountyco.gov/200/Land-Development-Code",
    },
    {
        "source_id": "county_lake_development_standards",
        "authority_id": "CO-COUNTY-LAKE",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.lakecountyco.com/DocumentCenter/View/157/Chapter-6--Development-Standards-PDF",
    },
    {
        "source_id": "county_laplata_code_portal",
        "authority_id": "CO-COUNTY-LA_PLATA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://online.encodeplus.com/regs/laplata-co/export2doc.aspx?amp%3Btocid=068&pdf=1",
    },
    {
        "source_id": "county_laplata_code_available_for_comment",
        "authority_id": "CO-COUNTY-LA_PLATA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://online.encodeplus.com/regs/laplata-co/rfc.aspx",
    },
    {
        "source_id": "county_larimer_policies_codes",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.larimer.gov/policies",
    },
    {
        "source_id": "county_larimer_land_use_code",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.larimer.gov/planning/land-use-code",
    },
    {
        "source_id": "county_larimer_code_compliance",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.larimer.gov/codecompliance",
    },
    {
        "source_id": "county_las_animas_archived_zoning",
        "authority_id": "CO-COUNTY-LAS_ANIMAS",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://hermes.cde.state.co.us/islandora/object/co%253A20152/datastream/OBJ/download/Las_Animas_County__Colorado_zoning_regulations.pdf",
    },
    {
        "source_id": "county_mesa_codes_regulations",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.mesacounty.us/departments-and-services/community-development/code-compliance-services/codes-and-regulations",
    },
    {
        "source_id": "county_mesa_current_land_development_code",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.mesacounty.us/departments-and-services/community-development/planning/current-land-development-code",
    },
    {
        "source_id": "county_mesa_land_development_code_pdf",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.mesacounty.us/sites/default/files/2024-10/Land%20Development%20Code%20-%202020%20%28Amended%2004-23-24%29.pdf",
    },
    {
        "source_id": "county_moffat_development_services",
        "authority_id": "CO-COUNTY-MOFFAT",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://moffatcounty.colorado.gov/services/office-of-development-services",
    },
    {
        "source_id": "county_moffat_floodplain_regulations",
        "authority_id": "CO-COUNTY-MOFFAT",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://moffatcounty.colorado.gov/sites/moffatcounty/files/March8_Docs_0.pdf",
    },
    {
        "source_id": "county_moffat_zoning_resolution_record",
        "authority_id": "CO-COUNTY-MOFFAT",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://moffatcounty.colorado.gov/sites/moffatcounty/files/Mar25_Docs_5.pdf",
    },
    {
        "source_id": "county_moffat_administrative_policies",
        "authority_id": "CO-COUNTY-MOFFAT",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://moffatcounty.colorado.gov/government/departments/finance-department/administrative-and-accounting-policies",
    },
    {
        "source_id": "county_montezuma_land_use_code_resolution",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://montezumacounty.gov/resolution-no-21-2020-the-montezuma-county-land-use-code/",
    },
    {
        "source_id": "county_montezuma_planning_zoning",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://montezumacounty.gov/planning-zoning/",
    },
    {
        "source_id": "county_montezuma_resolution_archive",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://montezumacounty.org/category/montezuma_county/bocc/resolution/",
    },
    {
        "source_id": "county_montrose_zoning_regulations",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.montrosecounty.net/228/Zoning-Regulations-Maps",
    },
    {
        "source_id": "county_montrose_zoning_regulations_current",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.montrosecounty.net/DocumentCenter/View/25696/Amended-Zoning-Regulations-2025-Remediated",
    },
    {
        "source_id": "county_montrose_resolution_index",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.montrosecounty.net/1300/2026-Resolution-Index-for-BOCC",
    },
    {
        "source_id": "county_montrose_site_map",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.montrosecounty.net/sitemap",
    },
    {
        "source_id": "county_morgan_zoning_regulations",
        "authority_id": "CO-COUNTY-MORGAN",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://morgancounty.colorado.gov/sites/morgancounty/files/documents/Zoning%20Regulations%20-%20September%202024.pdf",
    },
    {
        "source_id": "county_ouray_land_use_code",
        "authority_id": "CO-COUNTY-OURAY",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.ouraycountyco.gov/214/Land-Use-Code",
    },
    {
        "source_id": "county_ouray_land_use_planning_building",
        "authority_id": "CO-COUNTY-OURAY",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://ouraycountyco.gov/147/Land-Use-Planning",
    },
    {
        "source_id": "county_ouray_ordinances_resolutions",
        "authority_id": "CO-COUNTY-OURAY",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://ouraycountyco.gov/189/View",
    },
    {
        "source_id": "county_ouray_code_enforcement_resolution",
        "authority_id": "CO-COUNTY-OURAY",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://ouraycountyco.gov/DocumentCenter/View/20163/A-1------Expedited-Code-Enforcement-DRAFT-Resolution",
    },
    {
        "source_id": "county_park_land_use_regulations",
        "authority_id": "CO-COUNTY-PARK",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.parkcountyco.gov/189/Land-Use-Regulations",
    },
    {
        "source_id": "county_park_ordinances",
        "authority_id": "CO-COUNTY-PARK",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.parkcountyco.gov/551/County-Ordinances",
    },
    {
        "source_id": "county_park_resolutions_archive",
        "authority_id": "CO-COUNTY-PARK",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.parkcountyco.gov/Archive.aspx?AMID=63",
    },
    {
        "source_id": "county_park_ordinances_archive",
        "authority_id": "CO-COUNTY-PARK",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.parkcountyco.gov/Archive.aspx?AMID=65",
    },
    {
        "source_id": "county_park_development_services",
        "authority_id": "CO-COUNTY-PARK",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.parkcountyco.gov/85/Development-Services",
    },
    {
        "source_id": "county_otero_homepage_authority",
        "authority_id": "CO-COUNTY-OTERO",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://oterocounty.colorado.gov/",
    },
    {
        "source_id": "county_otero_land_use_building",
        "authority_id": "CO-COUNTY-OTERO",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://oterocounty.colorado.gov/commissioners/june-9-2025-public-hearing-agenda",
    },
    {
        "source_id": "county_otero_public_health_food",
        "authority_id": "CO-COUNTY-OTERO",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://oterocounty.colorado.gov/retail-food-restaurants-mobile-units",
    },
    {
        "source_id": "county_phillips_homepage_authority",
        "authority_id": "CO-COUNTY-PHILLIPS",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://phillipscounty.colorado.gov/",
    },
    {
        "source_id": "county_pitkin_code",
        "authority_id": "CO-COUNTY-PITKIN",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.pitkincounty.com/468/County-Code",
    },
    {
        "source_id": "county_pitkin_zoning",
        "authority_id": "CO-COUNTY-PITKIN",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.pitkincounty.com/1631/Zoning",
    },
    {
        "source_id": "county_pitkin_land_use",
        "authority_id": "CO-COUNTY-PITKIN",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.pitkincounty.com/196/Land-Use",
    },
    {
        "source_id": "county_pitkin_community_development",
        "authority_id": "CO-COUNTY-PITKIN",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.pitkincounty.com/1364/Community-Development",
    },
    {
        "source_id": "county_pitkin_growth_resources",
        "authority_id": "CO-COUNTY-PITKIN",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.pitkincounty.com/1461/Growth-Resources-and-Data",
    },
    {
        "source_id": "county_rio_grande_homepage_authority",
        "authority_id": "CO-COUNTY-RIO_GRANDE",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.riograndecounty.org/",
    },
    {
        "source_id": "county_routt_ordinances_resolutions",
        "authority_id": "CO-COUNTY-ROUTT",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://co.routt.co.us/439/Ordinances-Resolutions-Regulations",
    },
    {
        "source_id": "county_routt_land_use_code",
        "authority_id": "CO-COUNTY-ROUTT",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://co.routt.co.us/DocumentCenter/View/7346/Uses-By-Zone-District-Table",
    },
    {
        "source_id": "county_san_juan_planning",
        "authority_id": "CO-COUNTY-SAN_JUAN",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://sanjuancounty.colorado.gov/planning",
    },
    {
        "source_id": "county_san_juan_building_planning",
        "authority_id": "CO-COUNTY-SAN_JUAN",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://sanjuancounty.colorado.gov/planner",
    },
    {
        "source_id": "county_san_miguel_land_use_code",
        "authority_id": "CO-COUNTY-SAN_MIGUEL",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://sanmiguelcountyco.gov/243/Land-Use-Code",
    },
    {
        "source_id": "county_san_miguel_ordinances_resolutions",
        "authority_id": "CO-COUNTY-SAN_MIGUEL",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.sanmiguelcountyco.gov/655/Ordinances-and-Resolutions",
    },
    {
        "source_id": "county_san_miguel_planning",
        "authority_id": "CO-COUNTY-SAN_MIGUEL",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://sanmiguelcountyco.gov/198/Planning",
    },
    {
        "source_id": "county_teller_ordinances",
        "authority_id": "CO-COUNTY-TELLER",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.co.teller.co.us/County-Ordinances",
    },
    {
        "source_id": "county_teller_land_use_regulations",
        "authority_id": "CO-COUNTY-TELLER",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.co.teller.co.us/Teller-County-Land-Use-Regulations",
    },
    {
        "source_id": "county_teller_community_development",
        "authority_id": "CO-COUNTY-TELLER",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.co.teller.co.us/Community-Development-Department",
    },
    {
        "source_id": "county_teller_planning_zoning",
        "authority_id": "CO-COUNTY-TELLER",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.co.teller.co.us/Planning-Zoning-Division",
    },
    {
        "source_id": "county_summit_land_use_code",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.summitcountyco.gov/Documents/Services/Community%20Development/Planning/Board%20of%20Adjustment/DEV12_202207281556139524.pdf",
    },
    {
        "source_id": "county_washington_departments",
        "authority_id": "CO-COUNTY-WASHINGTON",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://washingtoncounty.colorado.gov/departments",
    },
    {
        "source_id": "county_weld_current_planning",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.weld.gov/Government/Departments/Planning-and-Development-Services/Planning-and-Zoning/Current-Planning",
    },
    {
        "source_id": "county_weld_planning_development",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.weld.gov/Government/Departments/Planning-and-Development-Services",
    },
    {
        "source_id": "county_weld_zoning_ordinance_2026_01",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.weld.gov/files/sharedassets/public/v/3/departments/planning-and-zoning/documents/long-range/code-changes/ord26-01.3rd-adopted.pdf",
    },
    {
        "source_id": "county_weld_building_ordinance_2026_05",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.weld.gov/Legal-and-Public-Notices/Commissioner-Notices/2026-Commissioner-Notices/Ordinance-2026-05-First-Reading",
    },
    {
        "source_id": "county_yuma_land_use",
        "authority_id": "CO-COUNTY-YUMA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://yumacounty.net/departments/land-use/",
    },
    {
        "source_id": "county_saguache_homepage_authority",
        "authority_id": "CO-COUNTY-SAGUACHE",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.saguachecounty.net/",
    },
    {
        "source_id": "county_broomfield_ordinances",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.broomfield.org/4283/City-Council-Ordinances",
    },
    {
        "source_id": "county_cheyenne_zoning_planning",
        "authority_id": "CO-COUNTY-CHEYENNE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.co.cheyenne.co.us/departments/zoning_planning.html",
    },
    {
        "source_id": "county_cheyenne_zoning_ordinance",
        "authority_id": "CO-COUNTY-CHEYENNE",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.co.cheyenne.co.us/assets/pdfs/zoning_comprehensive_plan_zoning_ordinance_2022.pdf",
    },
    {
        "source_id": "county_cheyenne_1041_regulations",
        "authority_id": "CO-COUNTY-CHEYENNE",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.co.cheyenne.co.us/assets/pdfs/zoning_1041_adopted_regs_2019.pdf",
    },
    {
        "source_id": "county_clear_creek_ordinances",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.clearcreekcounty.us/339/County-Ordinances",
    },
    {
        "source_id": "county_clear_creek_zoning_regulations",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.clearcreekcounty.us/288/Zoning-Regulations",
    },
    {
        "source_id": "county_clear_creek_site_map_codes",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.clearcreekcounty.us/SiteMap",
    },
    {
        "source_id": "county_clear_creek_building_permits",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://clearcreekcounty.us/1530/Permits",
    },
    {
        "source_id": "county_clear_creek_planning",
        "authority_id": "CO-COUNTY-CLEAR_CREEK",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://clearcreekcounty.us/124/Planning",
    },
    {
        "source_id": "county_crowley_homepage_authority",
        "authority_id": "CO-COUNTY-CROWLEY",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://crowleycounty.colorado.gov/",
    },
    {
        "source_id": "county_dolores_homepage_departments",
        "authority_id": "CO-COUNTY-DOLORES",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://dolocnty.colorado.gov/departments",
    },
    {
        "source_id": "county_dolores_land_use_regulations",
        "authority_id": "CO-COUNTY-DOLORES",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://dolocnty.colorado.gov/sites/dolocnty/files/documents/Land-Use-Regulations.pdf",
    },
    {
        "source_id": "county_dolores_homepage_transport_health",
        "authority_id": "CO-COUNTY-DOLORES",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://dolocnty.colorado.gov/",
    },
    {
        "source_id": "county_gilpin_commissioners_regulations",
        "authority_id": "CO-COUNTY-GILPIN",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://gilpincounty.colorado.gov/public-meetings/board-of-county-commissioners-bocc-meetings",
    },
    {
        "source_id": "county_hinsdale_homepage_ordinances_resolutions",
        "authority_id": "CO-COUNTY-HINSDALE",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://hinsdalecounty.colorado.gov/",
    },
    {
        "source_id": "county_hinsdale_zoning_map",
        "authority_id": "CO-COUNTY-HINSDALE",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://hinsdalecounty.colorado.gov/media/3321",
    },
    {
        "source_id": "county_lincoln_resolution_land_use",
        "authority_id": "CO-COUNTY-LINCOLN",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://lincolncounty.colorado.gov/sites/lincolncounty/files/03-28-25.pdf",
    },
    {
        "source_id": "county_lincoln_road_use_policy",
        "authority_id": "CO-COUNTY-LINCOLN",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://lincolncounty.colorado.gov/sites/lincolncounty/files/11-20-2024.pdf",
    },
    {
        "source_id": "county_mineral_land_use_regulations",
        "authority_id": "CO-COUNTY-MINERAL",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.mineralcountycolorado.com/land-use-office/page/land-use-regulations",
    },
    {
        "source_id": "county_mineral_zoning_regulations",
        "authority_id": "CO-COUNTY-MINERAL",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.mineralcountycolorado.com/media/486",
    },
    {
        "source_id": "county_mineral_construction_consent",
        "authority_id": "CO-COUNTY-MINERAL",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.mineralcountycolorado.com/land-use-office/page/mineral-county-land-use-and-construction-consent",
    },
    {
        "source_id": "county_mineral_clerk_records",
        "authority_id": "CO-COUNTY-MINERAL",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.mineralcountycolorado.com/clerk-recorder/page/clerk-board",
    },
    {
        "source_id": "county_mineral_owts_rules",
        "authority_id": "CO-COUNTY-MINERAL",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.mineralcountycolorado.com/land-use-office/page/site-wastewater-treatment-system-owts",
    },
    {
        "source_id": "county_sedgwick_homepage_authority",
        "authority_id": "CO-COUNTY-SEDGWICK",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://sedgwickcounty.colorado.gov/",
    },
    {
        "source_id": "county_archuleta_community_plan",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.archuletacounty.org/575/Community-Plan",
    },
    {
        "source_id": "county_baca_zoning_land_use",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.bacacountyco.gov/government/county-commissioners/zoning-permits-and-land-use/",
    },
    {
        "source_id": "county_baca_commissioners_ordinances",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.bacacountyco.gov/government/county-commissioners/",
    },
    {
        "source_id": "county_rio_blanco_planning",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://rbc.us/314/Planning",
    },
    {
        "source_id": "county_rio_blanco_land_use_regulations",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.rbc.us/DocumentCenter/View/6070/RBC-LUR_Current",
    },
    {
        "source_id": "county_rio_blanco_building",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://rbc.us/165/Building-Division",
    },
    {
        "source_id": "county_rio_blanco_floodplain",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://rbc.us/170/Floodplain-Development",
    },
    {
        "source_id": "county_rio_blanco_clerk_records",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://rbc.us/176/Clerk-Recorder",
    },
    {
        "source_id": "county_broomfield_charter_code",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.broomfield.org/3836/City-Charter-and-Code",
    },
    {
        "source_id": "county_broomfield_ordinances",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.broomfield.org/4283/City-Council-Ordinances",
    },
    {
        "source_id": "county_broomfield_zoning",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.broomfield.org/1979/Zoning",
    },
    {
        "source_id": "county_broomfield_planning",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.broomfield.org/planning",
    },
    {
        "source_id": "county_broomfield_building_code",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.broomfield.org/176/Building-Code-Information",
    },
    {
        "source_id": "county_broomfield_animal_ordinances",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://www.broomfield.org/1921/Animal-Ordinances",
    },
    {
        "source_id": "county_broomfield_wildfire_restrictions",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://broomfield.org/Wildfire",
    },
    {
        "source_id": "county_broomfield_alerts_fire",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.broomfield.org/AlertCenter.aspx",
    },
    {
        "source_id": "county_broomfield_building_department",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.broomfield.org/174/Building",
    },
    {
        "source_id": "county_broomfield_hazard_mitigation_plan",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://broomfield.org/DocumentCenter/View/44616/Final-HMP-Broomfield-_Jan2023",
    },
    {
        "source_id": "county_broomfield_legacy_zoning",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.broomfield.org/1979/Zoning",
    },
    {
        "source_id": "county_broomfield_council_procedures_resolution",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.broomfield.org/2738/Council-Procedures-and-Rules-of-Order",
    },
    {
        "source_id": "county_broomfield_meeting_archive",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.broomfield.org/4079/Broomfield-Council-Meetings",
    },
    {
        "source_id": "county_broomfield_resolution_2020_169",
        "authority_id": "CO-COUNTY-BROOMFIELD",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.broomfield.org/DocumentCenter/View/67310/Resolution-2020-169?bidId=",
    },
    {
        "source_id": "county_archuleta_fire_updates",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.archuletacounty.org/709/Fire-Updates-and-Information",
    },
    {
        "source_id": "county_archuleta_animal_control",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://www.archuletacounty.org/FAQ.aspx?QID=126",
    },
    {
        "source_id": "county_archuleta_planning_department",
        "authority_id": "CO-COUNTY-ARCHULETA",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://archuletacounty.org/93/Planning-Department",
    },
    {
        "source_id": "county_baca_departments",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.bacacountyco.gov/departments/",
    },
    {
        "source_id": "county_baca_emergency_management",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.bacacountyco.gov/departments/emergency-management/",
    },
    {
        "source_id": "county_baca_current_resolution_fire",
        "authority_id": "CO-COUNTY-BACA",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.bacacountyco.gov/",
    },
    {
        "source_id": "county_rio_blanco_alerts",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.rbc.us/alertcenter",
    },
    {
        "source_id": "county_rio_blanco_emergency_management",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.rbc.us/457/Emergency-Management",
    },
    {
        "source_id": "county_rio_blanco_departments",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.rbc.us/35/Departments",
    },
    {
        "source_id": "county_rio_blanco_sitemap_records",
        "authority_id": "CO-COUNTY-RIO_BLANCO",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.rbc.us/sitemap",
    },
    {
        "source_id": "county_logan_planning_zoning_building",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://www.logancountyco.gov/166/Planning-Zoning-Building-Department",
    },
    {
        "source_id": "county_logan_planning_applications",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.logancountyco.gov/321/Planning-and-Zoning-Applications",
    },
    {
        "source_id": "county_logan_commissioners_ordinances",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://www.logancountyco.gov/180/Logan-County-Commissioners",
    },
    {
        "source_id": "county_logan_links_documents",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.logancountyco.gov/268/Links-Documents",
    },
    {
        "source_id": "county_logan_commissioner_resolutions",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.logancountyco.gov/AgendaCenter/ViewFile/Agenda/_04072026-136",
    },
    {
        "source_id": "county_logan_building_applications",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.logancountyco.gov/321/Planning-and-Zoning-Applications",
    },
    {
        "source_id": "county_logan_roads_right_of_way",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://www.logancountyco.gov/321/Planning-and-Zoning-Applications",
    },
    {
        "source_id": "county_logan_zoning_code",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.logancountyco.gov/DocumentCenter/View/197/Logan-County-Zoning-Regulations-Updated-8-2019-PDF",
    },
    {
        "source_id": "county_logan_archive_center",
        "authority_id": "CO-COUNTY-LOGAN",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.logancountyco.gov/Archive.aspx",
    },
    {
        "source_id": "county_weld_outdoor_burning",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.weld.gov/Government/Departments/Health-and-Environment/Environmental-Health-Services/Air-Quality/Outdoor-Burning-Permits",
    },
    {
        "source_id": "county_weld_public_health_environment",
        "authority_id": "CO-COUNTY-WELD",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.weld.gov/files/sharedassets/public/v/1/departments/health-and-environment/documents/2024-annual-report.pdf",
    },
    {
        "source_id": "county_douglas_resolutions",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://publicnotices.douglas.co.us/board-of-county-commissioner-resolutions/",
    },
    {
        "source_id": "county_douglas_hazard_mitigation",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.douglas.co.us/wp-content/uploads/2026/03/Douglas-County-Hazard-Mitigation-Plan_Volume-2_Public_ReducedSize.pdf",
    },
    {
        "source_id": "county_douglas_rwr_archives",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.douglas.co.us/file-category/rwr/",
    },
    {
        "source_id": "county_douglas_public_health_archives",
        "authority_id": "CO-COUNTY-DOUGLAS",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.douglas.co.us/category/public-health/page/8/",
    },
    {
        "source_id": "county_summit_road_bridge_code",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://www.summitcountyco.gov/Documents/Services/Public%20Works/Road%20and%20Bridge/Maintained%20and%20Non%20Maintained%20Roads/DEV5_202207281553569850.pdf",
    },
    {
        "source_id": "county_summit_community_development",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://commdev.summitcountyco.gov/eTRAKiT3/",
    },
    {
        "source_id": "county_summit_good_neighbor_ordinance",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://summitcountyco.gov/Documents/Services/Community%20Development/Short%20Term%20Rentals/Good%20Neighbor%20Guidelines/Good%20Neighbor%20Guidelines%20Ordinance%2020-C%205.20.24.pdf",
    },
    {
        "source_id": "county_summit_wildfire_plan",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.summitcountyco.gov/Documents/Services/Community%20Development/CSU%20Extension/Forest%20Health/Wildfire%20Council/SCCWPP%202016%20Final%20Version_202009301111553168.pdf",
    },
    {
        "source_id": "county_summit_public_health_gis",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://gis.summitcountyco.gov/arcgis/rest/services/",
    },
    {
        "source_id": "county_montrose_fire_ordinance",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.montrosecounty.net/1170/Ordinance-2022-04",
    },
    {
        "source_id": "county_montrose_animal_ordinance",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://montrosecounty.net/1173/Ordinance-2022-01",
    },
    {
        "source_id": "county_montrose_resolution_index_2026",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.montrosecounty.net/1300/2026-Resolution-Index-for-BOCC",
    },
    {
        "source_id": "county_montrose_resolution_index_2022",
        "authority_id": "CO-COUNTY-MONTROSE",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://montrosecounty.net/DocumentCenter/View/18757/Resolution-Index-2022",
    },
    {
        "source_id": "county_montezuma_public_notices",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://montezumacounty.org/public-notices/2/",
    },
    {
        "source_id": "county_montezuma_ordinance_archive",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://montezumacounty.org/category/montezuma_county/bocc/ordinances/",
    },
    {
        "source_id": "county_montezuma_resolution_archive",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://montezumacounty.org/category/montezuma_county/bocc/resolution/",
    },
    {
        "source_id": "county_montezuma_fire_resolution",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://montezumacounty.org/resolutions-no-8-2025-a-resolution-reinstating-the-ban-on-open-fires-and-the-use-of-fireworks/",
    },
    {
        "source_id": "county_montezuma_road_animal_ordinances",
        "authority_id": "CO-COUNTY-MONTEZUMA",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://montezumacounty.org/category/montezuma_county/bocc/ordinances/",
    },
    {
        "source_id": "county_mesa_codes_regulations",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.mesacounty.us/departments-and-services/community-development/code-compliance-services/codes-and-regulations",
    },
    {
        "source_id": "county_mesa_animal_resolution",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://www.mesacounty.us/sites/default/files/2025-08/Resolution%202024-44%20%28updated%20Jan%202025%29ADA.pdf",
    },
    {
        "source_id": "county_mesa_fire_restrictions",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.mesacounty.us/departments-and-services/sheriff/divisions/emergency-services/fire-restrictions",
    },
    {
        "source_id": "county_mesa_commissioner_rules",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "continuing_resolutions",
        "url": "https://www.mesacounty.us/departments-and-services/commissioners/business-commissioners/meeting-types-rules",
    },
    {
        "source_id": "county_mesa_safety_action_plan",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://www.mesacounty.us/departments-and-services/rtpo/plans-programs-studies/mesa-county-safety-action-plan",
    },
    {
        "source_id": "county_mesa_open_records_archive",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.mesacounty.us/contact-us/open-records-request-mesa-county-cora",
    },
    {
        "source_id": "county_mesa_code_compliance_public_health",
        "authority_id": "CO-COUNTY-MESA",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.mesacounty.us/departments-and-services/community-development/code-compliance-services/complaint-process",
    },
    {
        "source_id": "county_moffat_traffic_ordinance",
        "authority_id": "CO-COUNTY-MOFFAT",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://moffatcounty.colorado.gov/sites/moffatcounty/files/Ord2024-0326-1stRding.pdf",
    },
    {
        "source_id": "county_las_animas_zoning_hermes",
        "authority_id": "CO-COUNTY-LAS_ANIMAS",
        "authority_level": "county",
        "category": "land_use_zoning",
        "url": "https://hermes.cde.state.co.us/islandora/object/co%253A20152/datastream/OBJ/download/Las_Animas_County__Colorado_zoning_regulations.pdf",
    },
    {
        "source_id": "county_las_animas_commissioners",
        "authority_id": "CO-COUNTY-LAS_ANIMAS",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://lasanimascounty.colorado.gov/elected-officials/commissioners",
    },
    {
        "source_id": "county_las_animas_land_use",
        "authority_id": "CO-COUNTY-LAS_ANIMAS",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://lasanimascounty.colorado.gov/departments/land-use-special-events-permit-application-bottom-of-page",
    },
    {
        "source_id": "county_las_animas_building",
        "authority_id": "CO-COUNTY-LAS_ANIMAS",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://lasanimascounty.colorado.gov/departments/building-department",
    },
    {
        "source_id": "county_jackson_homepage_authority",
        "authority_id": "CO-COUNTY-JACKSON",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://jacksoncounty.colorado.gov/",
    },
    {
        "source_id": "county_morgan_operations_emergency",
        "authority_id": "CO-COUNTY-MORGAN",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://morgancounty.colorado.gov/operations-division",
    },
    {
        "source_id": "county_morgan_ambulance_public_safety",
        "authority_id": "CO-COUNTY-MORGAN",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://morgancounty.colorado.gov/ambulance-service",
    },
    {
        "source_id": "county_morgan_archived_records",
        "authority_id": "CO-COUNTY-MORGAN",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://morgancounty.colorado.gov/archived-election-results",
    },
    {
        "source_id": "county_larimer_building_codes",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "building_construction",
        "url": "https://www.larimer.gov/building/building-codes/building_codes_adpoted_in_Larimer_County",
    },
    {
        "source_id": "county_larimer_road_access_standards",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "roads_transportation_access",
        "url": "https://www.larimer.gov/engineering-0/standards-and-guides",
    },
    {
        "source_id": "county_larimer_animal_code",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "animal_control_nuisance",
        "url": "https://www.larimer.gov/sites/default/files/uploads/2017/animal.pdf",
    },
    {
        "source_id": "county_larimer_fire_restrictions",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.larimer.gov/spotlights/2026/03/24/larimer-county-adopts-fire-restrictions",
    },
    {
        "source_id": "county_larimer_open_burning_ordinance",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "environmental_open_burning",
        "url": "https://www.larimer.gov/sites/default/files/ordinance_concerning_the_restriction_of_open_fires_-_2022_final_04262022.pdf",
    },
    {
        "source_id": "county_larimer_health_resolutions",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.larimer.gov/boards/board-health/proclamations-and-resolutions",
    },
    {
        "source_id": "county_larimer_continuing_policies",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "administrative_rule_manuals",
        "url": "https://www.larimer.gov/policies",
    },
    {
        "source_id": "county_larimer_archived_building_codes",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "archived_versions",
        "url": "https://www.larimer.gov/sites/default/files/uploads/2022/building_codes_adopted_in_larimer_county.pdf",
    },
    {
        "source_id": "county_summit_development_code",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "county_codes",
        "url": "https://www.summitcountyco.gov/Documents/Services/Community%20Development/Planning/Projects%20Under%20Review/PLN23-085/Combined%20meeting%20materials%2002.5.2024%20CWPC.pdf",
    },
    {
        "source_id": "county_summit_development_code_ordinance",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "county_ordinances",
        "url": "https://summitcountyco.gov/Documents/Services/Community%20Development/Short%20Term%20Rentals/License%20Application/Ordinance%2020-C%20Summit%20County%20STR%20Acknowledgements%20and%20Affidavit_202303061315075936.pdf",
    },
    {
        "source_id": "county_summit_subdivision_code",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "subdivision_development",
        "url": "https://www.summitcountyco.gov/Documents/Services/Information%20Systems%20and%20GIS/GIS/DEV8_201909171055422409.pdf",
    },
    {
        "source_id": "county_summit_wildfire_restrictions_reference",
        "authority_id": "CO-COUNTY-SUMMIT",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://summitcountyco.gov/Documents/Services/Community%20Development/Short%20Term%20Rentals/Good%20Neighbor%20Guidelines/Good%20Neighbor%20Guidelines%20Ordinance%2020-C%205.20.24.pdf",
    },
    {
        "source_id": "county_la_plata_wildfire_code",
        "authority_id": "CO-COUNTY-LA_PLATA",
        "authority_level": "county",
        "category": "emergency_fire_restrictions",
        "url": "https://www.co.laplata.co.us/emergency%20management/Wildfire/Concept%20Wildfire%20Preparedness%20Code%20July%2023.pdf",
    },
    {
        "source_id": "county_la_plata_public_health_fee_schedule",
        "authority_id": "CO-COUNTY-LA_PLATA",
        "authority_level": "county",
        "category": "public_health",
        "url": "https://www.co.laplata.co.us/Public%20Health/2024%20LPCPH%20Fee%20Schedule%20Final.pdf",
    },
)

SEED_CATEGORY_ALIASES = {
    "county_boulder_ordinances": (
        "animal_control_nuisance",
        "public_health",
        "environmental_open_burning",
        "roads_transportation_access",
        "continuing_resolutions",
        "emergency_fire_restrictions",
    ),
    "county_boulder_land_use_code": ("subdivision_development", "building_construction"),
    "county_garfield_land_use_development_code": (
        "subdivision_development",
        "roads_transportation_access",
        "animal_control_nuisance",
        "building_construction",
    ),
    "county_pueblo_code": (
        "county_ordinances",
        "animal_control_nuisance",
        "public_health",
        "roads_transportation_access",
        "building_construction",
        "continuing_resolutions",
        "administrative_rule_manuals",
    ),
    "county_alamosa_board_ordinances": (
        "building_construction",
        "roads_transportation_access",
        "animal_control_nuisance",
        "environmental_open_burning",
    ),
    "county_alamosa_land_use_building": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_archuleta_land_use_general": ("subdivision_development", "building_construction"),
    "county_archuleta_quick_links": (
        "building_construction",
        "public_health",
        "roads_transportation_access",
        "animal_control_nuisance",
    ),
    "county_chaffee_land_use_code": (
        "subdivision_development",
        "roads_transportation_access",
        "building_construction",
    ),
    "county_clear_creek_source_map": (
        "county_ordinances",
        "land_use_zoning",
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_custer_zoning_regulations": (
        "subdivision_development",
        "building_construction",
    ),
    "county_delta_land_use_regulations": (
        "subdivision_development",
        "roads_transportation_access",
        "building_construction",
        "continuing_resolutions",
    ),
    "county_delta_building_land_use_subdivision": (
        "land_use_zoning",
        "roads_transportation_access",
    ),
    "county_conejos_construction_permit_instructions": (
        "land_use_zoning",
        "administrative_rule_manuals",
    ),
    "county_costilla_planning_zoning": (
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_costilla_planning_resources": (
        "roads_transportation_access",
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_costilla_land_use_code": (
        "land_use_zoning",
        "subdivision_development",
        "roads_transportation_access",
    ),
    "county_denver_regulations_codes_standards": (
        "county_ordinances",
        "building_construction",
        "land_use_zoning",
        "roads_transportation_access",
        "continuing_resolutions",
    ),
    "county_denver_zoning_code": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_denver_archived_building_codes": (
        "building_construction",
    ),
    "county_eagle_land_use_regulations": (
        "subdivision_development",
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_elbert_regulations": (
        "subdivision_development",
        "building_construction",
        "animal_control_nuisance",
        "environmental_open_burning",
        "roads_transportation_access",
    ),
    "county_elbert_recorded_ordinances_resolutions": (
        "continuing_resolutions",
        "roads_transportation_access",
        "emergency_fire_restrictions",
        "environmental_open_burning",
    ),
    "county_elbert_building_code_ordinance": ("county_codes",),
    "county_elpaso_ordinances": (
        "county_codes",
        "continuing_resolutions",
        "emergency_fire_restrictions",
    ),
    "county_elpaso_land_development_code": (
        "subdivision_development",
        "roads_transportation_access",
        "building_construction",
    ),
    "county_elpaso_land_development_uses": ("building_construction", "roads_transportation_access"),
    "county_fremont_zoning_resolution": (
        "subdivision_development",
        "building_construction",
    ),
    "county_fremont_zoning_regulations_pdf": ("subdivision_development",),
    "county_fremont_commissioner_records": (
        "continuing_resolutions",
        "roads_transportation_access",
    ),
    "county_grand_planning_zoning": (
        "subdivision_development",
        "roads_transportation_access",
        "administrative_rule_manuals",
    ),
    "county_grand_building_development": (
        "subdivision_development",
        "roads_transportation_access",
        "environmental_open_burning",
        "administrative_rule_manuals",
    ),
    "county_gunnison_land_use_resolution": (
        "subdivision_development",
        "roads_transportation_access",
        "animal_control_nuisance",
        "continuing_resolutions",
    ),
    "county_gunnison_land_use_energy_environment": (
        "public_health",
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_gunnison_building_office": ("administrative_rule_manuals",),
    "county_gunnison_community_development": (
        "public_health",
        "building_construction",
        "environmental_open_burning",
    ),
    "county_huerfano_land_use_building": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
        "administrative_rule_manuals",
    ),
    "county_huerfano_proposed_land_use_code": (
        "land_use_zoning",
        "subdivision_development",
        "building_construction",
    ),
    "county_huerfano_news_ordinances_fire": (
        "continuing_resolutions",
        "emergency_fire_restrictions",
        "building_construction",
    ),
    "county_kit_carson_land_use": (
        "subdivision_development",
        "roads_transportation_access",
        "building_construction",
        "public_health",
        "administrative_rule_manuals",
    ),
    "county_kit_carson_homepage_resolutions_fire": (
        "county_ordinances",
        "emergency_fire_restrictions",
        "archived_versions",
    ),
    "county_kit_carson_solid_waste": ("administrative_rule_manuals",),
    "county_jackson_comprehensive_plan": (
        "subdivision_development",
        "roads_transportation_access",
        "building_construction",
    ),
    "county_kiowa_commissioners_resolutions": (
        "county_ordinances",
        "roads_transportation_access",
        "emergency_fire_restrictions",
    ),
    "county_kiowa_resolutions_archive": (
        "archived_versions",
        "administrative_rule_manuals",
    ),
    "county_kiowa_building_code_resolution": (
        "county_codes",
        "administrative_rule_manuals",
    ),
    "county_kiowa_comprehensive_plan": (
        "subdivision_development",
        "roads_transportation_access",
        "public_health",
    ),
    "county_lake_land_development_code": (
        "land_use_zoning",
        "building_construction",
        "roads_transportation_access",
        "environmental_open_burning",
        "administrative_rule_manuals",
    ),
    "county_lake_development_standards": (
        "roads_transportation_access",
        "building_construction",
    ),
    "county_laplata_code_portal": (
        "county_ordinances",
        "land_use_zoning",
        "subdivision_development",
        "building_construction",
        "public_health",
        "environmental_open_burning",
        "roads_transportation_access",
        "animal_control_nuisance",
        "emergency_fire_restrictions",
        "continuing_resolutions",
        "administrative_rule_manuals",
    ),
    "county_laplata_code_available_for_comment": ("archived_versions",),
    "county_larimer_policies_codes": (
        "building_construction",
        "administrative_rule_manuals",
        "continuing_resolutions",
    ),
    "county_larimer_land_use_code": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
        "environmental_open_burning",
    ),
    "county_larimer_code_compliance": (
        "animal_control_nuisance",
        "continuing_resolutions",
        "emergency_fire_restrictions",
    ),
    "county_routt_ordinances_resolutions": (
        "county_codes",
        "public_health",
        "environmental_open_burning",
        "roads_transportation_access",
        "animal_control_nuisance",
        "emergency_fire_restrictions",
        "administrative_rule_manuals",
        "archived_versions",
    ),
    "county_routt_land_use_code": (
        "subdivision_development",
        "building_construction",
    ),
    "county_las_animas_archived_zoning": (
        "land_use_zoning",
        "subdivision_development",
    ),
    "county_mesa_codes_regulations": (
        "county_ordinances",
        "public_health",
        "environmental_open_burning",
        "animal_control_nuisance",
        "administrative_rule_manuals",
    ),
    "county_mesa_current_land_development_code": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_mesa_land_development_code_pdf": (
        "archived_versions",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_moffat_development_services": (
        "land_use_zoning",
        "subdivision_development",
        "administrative_rule_manuals",
    ),
    "county_moffat_floodplain_regulations": (
        "public_health",
        "roads_transportation_access",
    ),
    "county_moffat_zoning_resolution_record": (
        "continuing_resolutions",
        "subdivision_development",
    ),
    "county_moffat_administrative_policies": ("continuing_resolutions",),
    "county_montezuma_land_use_code_resolution": (
        "land_use_zoning",
        "subdivision_development",
        "building_construction",
        "animal_control_nuisance",
        "roads_transportation_access",
    ),
    "county_montezuma_planning_zoning": ("administrative_rule_manuals",),
    "county_montezuma_resolution_archive": (
        "continuing_resolutions",
        "archived_versions",
    ),
    "county_montrose_zoning_regulations": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_montrose_zoning_regulations_current": ("archived_versions",),
    "county_montrose_resolution_index": (
        "emergency_fire_restrictions",
        "continuing_resolutions",
    ),
    "county_montrose_site_map": (
        "county_ordinances",
        "building_construction",
        "public_health",
        "administrative_rule_manuals",
    ),
    "county_morgan_zoning_regulations": (
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
    ),
    "county_ouray_land_use_code": (
        "subdivision_development",
        "roads_transportation_access",
        "emergency_fire_restrictions",
        "environmental_open_burning",
    ),
    "county_ouray_land_use_planning_building": (
        "subdivision_development",
        "administrative_rule_manuals",
    ),
    "county_ouray_ordinances_resolutions": (
        "continuing_resolutions",
        "archived_versions",
        "public_health",
    ),
    "county_ouray_code_enforcement_resolution": (
        "building_construction",
        "administrative_rule_manuals",
    ),
    "county_park_land_use_regulations": (
        "land_use_zoning",
        "subdivision_development",
        "building_construction",
        "roads_transportation_access",
        "environmental_open_burning",
    ),
    "county_park_ordinances": (
        "animal_control_nuisance",
        "public_health",
        "emergency_fire_restrictions",
    ),
    "county_park_resolutions_archive": (
        "archived_versions",
        "roads_transportation_access",
    ),
    "county_park_ordinances_archive": (
        "archived_versions",
        "roads_transportation_access",
    ),
    "county_park_development_services": (
        "public_health",
        "administrative_rule_manuals",
    ),
}


def build_county_matrix() -> dict[str, Any]:
    """Build a complete county-by-source-category coverage matrix."""

    today = date.today().isoformat()
    counties = []
    for name in COUNTY_NAMES:
        county_id = "CO-COUNTY-" + name.upper().replace(" ", "_")
        counties.append(
            {
                "county_id": county_id,
                "county_name": f"{name} County" if name != "Denver" else "City and County of Denver",
                "source_categories": {
                    category: {"status": "not_started", "source_ids": [], "notes": ""}
                    for category in SOURCE_CATEGORIES
                },
                "overall_status": "not_started",
                "last_checked": today,
            }
        )
    return {
        "state": "CO",
        "county_count": len(counties),
        "source_categories": list(SOURCE_CATEGORIES),
        "status_values": [
            "not_started",
            "source_identified",
            "downloaded",
            "downloaded_unreviewed",
            "partial",
            "complete",
            "blocked",
        ],
        "counties": counties,
    }


def write_county_matrix(root: Path) -> Path:
    """Write the statewide county coverage matrix."""

    path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    atomic_write_json(path, build_county_matrix(), root)
    return path


def register_county_homepages(root: Path) -> Path:
    """Add verified county homepages to the local source registry."""

    registry_path = root / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json"
    registry = load_json(registry_path)
    existing = {entry["authority_id"]: entry for entry in registry.get("pilot", {}).get("counties", [])}
    counties = []
    for name in COUNTY_NAMES:
        authority_id = "CO-COUNTY-" + name.upper().replace(" ", "_")
        current = dict(existing.get(authority_id, {}))
        current.setdefault("source_id", f"county_{name.lower().replace(' ', '_')}_homepage")
        current["authority_id"] = authority_id
        current["authority_level"] = "county"
        current.setdefault("authority_type", "city_and_county" if name == "Denver" else "county")
        current.setdefault("name", "City and County of Denver" if name == "Denver" else f"{name} County")
        current.setdefault("county_names", [f"{name} County"])
        current["url"] = current.get("url") or COUNTY_HOME_URLS[name]
        current.setdefault("access_method", "official_county_homepage")
        current.setdefault("known_gaps", ["County legal source categories require separate discovery."])
        counties.append(current)
    registry.setdefault("pilot", {})["counties"] = counties
    registry["coverage_boundary"] = (
        "All 64 Colorado county homepages are registered from the official state county directory; "
        "legal source category collection remains in progress."
    )
    atomic_write_json(registry_path, registry, root)
    return registry_path


def update_homepage_coverage(root: Path) -> Path:
    """Record homepage download results in the county coverage matrix."""

    matrix_path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    manifest_path = root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    matrix = load_json(matrix_path)
    latest: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(manifest_path):
        if row.get("authority_level") == "county" and row.get("requested_url") == row.get("source_url"):
            latest[str(row["authority_id"])] = row
    for county in matrix.get("counties", []):
        row = latest.get(str(county["county_id"]))
        if not row:
            continue
        county["homepage"] = {
            "url": row.get("source_url"),
            "status": "downloaded" if row.get("status") == "downloaded" else "blocked",
            "source_id": row.get("source_id"),
            "raw_path": row.get("raw_path"),
            "message": row.get("message", ""),
        }
        county["overall_status"] = "source_identified" if row.get("status") == "downloaded" else "blocked"
    atomic_write_json(matrix_path, matrix, root)
    return matrix_path


def register_seed_sources(root: Path) -> Path:
    """Add verified category-specific sources discovered in the first wave."""

    registry_path = root / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json"
    registry = load_json(registry_path)
    pilot = registry.setdefault("pilot", {})
    existing = {row["source_id"]: row for row in pilot.get("county_sources", [])}
    for row in SEED_SOURCE_RECORDS:
        existing[row["source_id"]] = dict(row)
        for category in SEED_CATEGORY_ALIASES.get(row["source_id"], ()):
            alias = dict(row)
            alias["source_id"] = f"{row['source_id']}_{category}"
            alias["category"] = category
            existing[alias["source_id"]] = alias
    pilot["county_sources"] = list(existing.values())
    atomic_write_json(registry_path, registry, root)
    return registry_path


def update_category_coverage(root: Path) -> Path:
    """Apply registered category-source download results to the coverage matrix."""

    matrix_path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    registry = load_json(root / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json")
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in iter_jsonl(root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"):
        rows_by_source.setdefault(str(row.get("source_id")), []).append(row)
    matrix = load_json(matrix_path)
    counties = {str(row["county_id"]): row for row in matrix.get("counties", [])}
    for source in registry.get("pilot", {}).get("county_sources", []):
        county = counties.get(str(source.get("authority_id")))
        if not county:
            continue
        category = str(source.get("category"))
        if category not in county.get("source_categories", {}):
            continue
        attempts = rows_by_source.get(str(source["source_id"]), [])
        if not attempts:
            continue
        successful = [row for row in attempts if row.get("status") == "downloaded"]
        target = county["source_categories"][category]
        target["source_ids"] = sorted(set(target.get("source_ids", [])) | {source["source_id"]})
        if successful:
            target["status"] = "downloaded"
            target["notes"] = "Official source preserved; normalization and category review remain pending."
        elif target.get("status") != "blocked" or "Documented official-source gap" not in str(
            target.get("notes", "")
        ):
            target["status"] = "blocked"
            target["notes"] = "Official source attempt failed; see download manifest for details."
    for row in iter_jsonl(root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"):
        if row.get("status") != "downloaded" or row.get("authority_level") != "county":
            continue
        requested_url = str(row.get("requested_url") or "")
        source_url = str(row.get("source_url") or "")
        if requested_url == source_url:
            continue
        compact = re.sub(r"[^a-z0-9]", "", (requested_url + " " + str(row.get("raw_path"))).casefold())
        county = counties.get(str(row.get("authority_id")))
        if not county:
            continue
        for category, terms in CATEGORY_TERM_MAP.items():
            if not any(term in compact for term in terms):
                continue
            target = county["source_categories"][category]
            if target["status"] == "not_started":
                target["status"] = "downloaded_unreviewed"
            target["source_ids"] = sorted(set(target.get("source_ids", [])) | {str(row["source_id"])})
            target["notes"] = "Raw source downloaded; category assignment is heuristic and needs review."
        if county.get("overall_status") == "source_identified":
            county["overall_status"] = "partial"
    atomic_write_json(matrix_path, matrix, root)
    return matrix_path


def main() -> int:
    """Write the statewide coverage matrix from the repository root."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--register-homepages", action="store_true")
    parser.add_argument("--update-homepage-coverage", action="store_true")
    parser.add_argument("--register-seed-sources", action="store_true")
    parser.add_argument("--update-category-coverage", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    matrix_path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    print(matrix_path if matrix_path.exists() else write_county_matrix(root))
    if args.register_homepages:
        print(register_county_homepages(root))
    if args.update_homepage_coverage:
        print(update_homepage_coverage(root))
    if args.register_seed_sources:
        print(register_seed_sources(root))
    if args.update_category_coverage:
        print(update_category_coverage(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
