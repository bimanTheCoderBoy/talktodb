
table_context = """
# Database Schema Template
Converted from the provided JSON into a readable Markdown format.
## cell_lte
**table_des:** LTE cell configuration & operational metadata including identifiers, location, RF parameters, MIMO/beamforming support, load, and timestamps.

- **bvid** : text -> Project Name
- **location_iid** : text -> Location object's unique identifier (site)
- **iid** : text -> Unique identifier for the cell, Name of the cell
- **technology_active** : text -> Active radio technology (should be LTE)
- **technology_fixed** : boolean -> Fixed radio technology
- **mu_iid** : text -> MU node internal identifier`
- **lte_eci** : integer -> LTE E-UTRAN Cell Identifier
- **lte_ecgi** : text -> LTE E-UTRAN Cell Global Identifier (ECGI)
- **lte_tac** : integer -> Tracking Area Code
- **lte_firstassignedrsi** : integer -> First Assigned RACH Root Sequence Index (RSI)
- **lte_numberassignedrsi** : integer -> Number of assigned RSI values
- **lte_carrierparameters_physicalcellid** : integer -> Physical Cell ID (PCI)
- **lte_carrierparameters_pcigroup_ro** : integer -> PCI Group (PCI / 3) — read-only
- **lte_carrierparameters_pcicode_ro** : integer -> PCI Code (PCI mod 3) — read-only
- **lte_carrierparameters_maxrange** : double precision -> Maximum cell range in km
- **lte_carrierparameters_noisefigure** : double precision -> Noise figure (dB)
- **lte_carrierparameters_maxtxpower** : double precision -> Maximum configured transmit power (dBm)
- **lte_carrierparameters_referencesignalppre** : double precision -> Reference Signal Power Per Resource Element (dBm)
- **lte_carrierparameters_iid** : text -> LTE carrier parameters identifier — encodes the carrier, band AND bandwidth (e.g., 'L800_10M_6400' means Band 800 MHz, 10 MHz bandwidth, EARFCN 6400). THIS IS THE PRIMARY COLUMN for band/frequency/carrier queries. Group by this to find cells on same band.
- **lte_carrierparameters_rsrp** : double precision -> Configured RSRP target (dBm)
- **lte_carrierparameters_rsrpthreshold** : double precision -> RSRP threshold (dBm)
- **lte_carrierparameters_rsrpoffset** : double precision -> RSRP offset value (dB)
- **lte_carrierparameters_modulationkey** : text -> Modulation scheme key
- **lte_carrierparameters_caenabledatcell** : boolean -> Carrier Aggregation enabled at cell
- **lte_carrierparameters_schedulerkey** : text -> Scheduler/profile key for cell resource allocation
- **lte_carrierparameters_maxscheduledusers** : integer -> Maximum scheduled users
- **lte_carrierparameters_sinrthreshold** : double precision -> SINR threshold (dB)
- **lte_carrierparameters_celledgethreshmode** : text -> Cell edge threshold mode
- **lte_carrierparameters_trafficoffset** : double precision -> Traffic channel power offset (dB)
- **lte_carrierparameters_controloffset** : double precision -> Control channel power offset (dB)
- **lte_carrierparameters_syncoffset** : double precision -> Sync channel power offset (dB)
- **lte_carrierparameters_broadcastoffset** : double precision -> Broadcast channel power offset (dB)
- **lte_nbrlimitintraintra** : integer -> Intra-frequency intra-RAT neighbor limit
- **lte_nbrlimitintrainter** : integer -> Inter-frequency intra-RAT neighbor limit
- **lte_nbrlimitintergsm** : integer -> Neighbor limit towards GSM
- **lte_nbrlimitinterumts** : integer -> Neighbor limit towards UMTS
- **lte_nbrlimitinterfiveg** : integer -> Neighbor limit towards 5G NR
- **lte_nbrlimitalltechs** : integer -> Total neighbor limit across all technologies
- **lte_carrierparameters_timingadvanceenabled** : boolean -> Whether timing advance is enabled
- **lte_carrierparameters_maxta** : double precision -> Maximum timing advance value
- **lte_sumimosupportdl** : boolean -> Single User MIMO support for downlink
- **lte_sumimospatialmodedl** : text -> SU-MIMO spatial mode for downlink
- **lte_sumimotxelems** : integer -> Number of SU-MIMO transmit elements
- **lte_sumimosupportul** : boolean -> Single User MIMO support for uplink
- **lte_mumimosupportdl** : boolean -> Multi-User MIMO support for downlink
- **lte_mumimotermsdl** : double precision -> MU-MIMO terms for downlink
- **lte_beamformingsupportdl** : boolean -> Beamforming support for downlink
- **lte_beamformertype** : text -> Beamformer type
- **lte_beamformingarrayelems** : integer -> Number of beamforming array elements
- **lte_highspeedflag** : boolean -> High-speed cell flag (for HST/train coverage)
- **lte_actualrange_ro** : double precision -> Actual calculated cell range in km (read-only)
- **lte_signallingoverhead** : double precision -> Signalling overhead percentage
- **lte_activation** : boolean -> Whether cell is activated/active
- **lte_carrierparameters_cellload_cellcentredl** : double precision -> Cell center downlink load (%)
- **lte_carrierparameters_cellload_cellcentreul** : double precision -> Cell center uplink load (%)
- **lte_carrierparameters_cellload_celledgedl** : double precision -> Cell edge downlink load (%)
- **lte_carrierparameters_cellload_celledgeul** : double precision -> Cell edge uplink load (%)
- **lte_carrierparameters_cellload_avgnumofconnusers** : integer -> Average number of connected users
- **lte_carrierparameters_dsssupportdl** : boolean -> Dynamic Spectrum Sharing support downlink
- **lte_carrierparameters_dsssupportul** : boolean -> Dynamic Spectrum Sharing support uplink
- **lte_prachfrequencyoffset** : integer -> PRACH frequency offset
- **lte_carrierparameters_cellspecificfreqshift_ro** : text -> Cell-specific frequency shift (read-only)
- **security_createdate** : timestamp without time zone -> Timestamp when the record was created
- **security_modifydate** : timestamp without time zone -> Timestamp when the record was last modified
- **imported_at** : timestamp without time zone -> Timestamp when the record was imported

## cell_nr
**table_des:** NR (5G) cell configuration & operational metadata including identifiers, location, RF parameters, MIMO/beamforming support, load, and timestamps.

- **bvid** : text -> Project Name
- **location_iid** : text -> Location object's unique identifier (site)
- **iid** : text -> Unique identifier for the cell, Name of the cell
- **technology_active** : text -> Active radio technology (should be NR)
- **technology_fixed** : boolean -> Fixed radio technology
- **mu_iid** : text -> MU node internal identifier
- **nrt_tac** : integer -> NR Tracking Area Code
- **nrt_tacformat** : text -> TAC format
- **nrt_carrierparameters_physicalcellid** : integer -> Physical Cell ID (PCI)
- **nrt_carrierparameters_maxrange** : double precision -> Maximum cell range in km
- **nrt_carrierparameters_noisefigure** : double precision -> Noise figure (dB)
- **nrt_carrierparameters_maxtxpower** : double precision -> Maximum configured transmit power (dBm)
- **nrt_carrierparameters_ssrsrpthreshold** : double precision -> SS-RSRP threshold (dBm)
- **nrt_carrierparameters_csirsrpthreshold** : double precision -> CSI-RSRP threshold (dBm)
- **nrt_carrierparameters_rsrpoffset** : double precision -> RSRP offset value (dB)
- **nrt_nbrlimitintraintra** : integer -> Intra-frequency intra-RAT neighbor limit
- **nrt_nbrlimitinterlte** : integer -> Neighbor limit towards LTE
- **nrt_carrierparameters_timingadvancedenabled** : boolean -> Whether timing advance is enabled
- **nrt_carrierparameters_maxta** : double precision -> Maximum timing advance value
- **nrt_sumimosupportdl** : boolean -> Single User MIMO support for downlink
- **nrt_sumimospatialmodedl** : text -> SU-MIMO spatial mode for downlink
- **nrt_sumimotxelems** : integer -> Number of SU-MIMO transmit elements
- **nrt_carrierparameters_iid** : text -> NR carrier parameters identifier — encodes the carrier/band (e.g., 'N3500', 'N700'). USE THIS to group NR cells by same band/frequency/carrier.
- **nrt_carrierparameters_prachfrequencystart** : integer -> PRACH frequency start for NR
- **nrt_carrierparameters_cellbandwidthparts_iid** : text -> NR cell bandwidth part identifier
- **nrt_carrierparameters_cellbandwidthparts_downlink_startarfcn** : integer -> NR downlink start ARFCN (frequency point number)
- **nrt_carrierparameters_cellbandwidthparts_uplink_startarfcn** : integer -> NR uplink start ARFCN (frequency point number)
- **nrt_carrierparameters_cellbandwidthparts_downlink_prbs** : integer -> Number of downlink Physical Resource Blocks
- **nrt_carrierparameters_cellbandwidthparts_uplink_prbs** : integer -> Number of uplink Physical Resource Blocks
- **nrt_carrierparameters_cellbandwidthparts_downlink_numerology** : text -> Downlink numerology (subcarrier spacing)
- **nrt_carrierparameters_cellbandwidthparts_ssbnumerology** : text -> SSB numerology
- **nrt_carrierparameters_cellbandwidthparts_tddslotparametersdl** : double precision -> TDD slot parameters downlink ratio
- **nrt_carrierparameters_cellbandwidthparts_tddslotparametersul** : double precision -> TDD slot parameters uplink ratio
- **nrt_carrierparameters_cellbandwidthparts_cellloadpcntdl** : double precision -> NR cell load percentage downlink
- **nrt_carrierparameters_cellbandwidthparts_cellloadpcntul** : double precision -> NR cell load percentage uplink
- **nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers** : integer -> NR average connected users
- **security_createdate** : timestamp without time zone -> Timestamp when the record was created
- **security_modifydate** : timestamp without time zone -> Timestamp when the record was last modified
- **imported_at** : timestamp without time zone -> Timestamp when the record was imported

## cell_physical_antenna
**table_des:** Physical antenna configuration — azimuth, mechanical tilt, height, coordinates, antenna type, and constraints. JOIN with cell_lte/cell_nr via cell_iid. This is THE table for tilt, azimuth, height queries.
**join_key:** cell_iid (matches cell_lte.cell_iid or cell_nr.cell_iid)

- **cell_iid** : text -> Linked cell unique identifier — USE FOR JOIN with cell_lte/cell_nr
- **azimuth** : float -> Antenna azimuth angle in degrees (0-360)
- **tilt** : float -> Antenna MECHANICAL tilt in degrees (this is mechanical tilt, NOT electrical)
- **twist** : float -> Antenna twist angle in degrees
- **height** : float -> Antenna height above ground in meters
- **heightpred** : float -> Predicted antenna height
- **heightpredoffset** : float -> Predicted height offset
- **spatialdiversity** : boolean -> Whether spatial diversity is enabled
- **antennatype_ro** : text -> Antenna type/model name (read-only)
- **antennadevice_iid** : text -> Antenna device identifier
- **abslocation_longitude** : float -> Absolute longitude coordinate
- **abslocation_latitude** : float -> Absolute latitude coordinate
- **constraints_azimuthfixed** : boolean -> Whether azimuth is fixed/locked
- **constraints_heightfixed** : boolean -> Whether height is fixed/locked
- **constraints_mechanicaltiltfixed** : boolean -> Whether mechanical tilt is fixed/locked
- **constraints_minmechanicaltilt_value** : integer -> Minimum mechanical tilt allowed (degrees)
- **constraints_maxmechanicaltilt_value** : integer -> Maximum mechanical tilt allowed (degrees)
- **constraints_mechanicaltiltstep_value** : integer -> Step increment for mechanical tilt (degrees)
- **location_iid** : text -> Location (site) unique identifier
- **mu_iid** : text -> MU node unique identifier
- **imported_at** : timestamp without time zone -> Timestamp when record was imported

## cell_logical_antenna
**table_des:** Logical antenna parameters — electrical tilt, total tilt, propagation models, beamforming, beam switching. JOIN with cell_lte/cell_nr via cell_iid. This is THE table for electrical tilt and total tilt queries.
**join_key:** cell_iid (matches cell_lte.cell_iid or cell_nr.cell_iid)

- **cell_iid** : text -> Linked cell unique identifier — USE FOR JOIN with cell_lte/cell_nr
- **passive_electricaldowntilt_ro** : float -> Electrical downtilt value in degrees (READ-ONLY)
- **passive_totaldowntilt_ro** : float -> Total downtilt = mechanical + electrical tilt (READ-ONLY)
- **passive_patternfrequency_ro** : float -> Antenna pattern frequency in MHz
- **passive_antennapatternangle_ro** : float -> Antenna pattern angle
- **antennatype_ro** : text -> Antenna type/model (read-only)
- **singlebeamenabled** : boolean -> Whether single beam is enabled
- **correctionfactor** : float -> DL correction factor
- **ulcorrectionfactor** : float -> UL correction factor
- **primarymodel_radiuskm** : float -> Primary propagation model radius in km
- **primarymodel_modeltype_iid** : text -> Primary model type identifier
- **constraints_totalmaximumdowntilt_value** : integer -> Max total downtilt allowed (degrees)
- **constraints_totalminimumdowntilt_value** : integer -> Min total downtilt allowed (degrees)
- **constraints_electricalmaximumdowntilt_value** : integer -> Max electrical downtilt (degrees)
- **constraints_electricalminimumdowntilt_value** : integer -> Min electrical downtilt (degrees)
- **constraints_electricaldowntiltstep_value** : integer -> Electrical tilt step size (degrees)
- **location_iid** : integer -> Location (site) unique identifier
- **mu_iid** : text -> MU node unique identifier
- **imported_at** : timestamp without time zone -> Timestamp when the record was imported

## mu_lte
**table_des:** LTE Management Unit (base station) configuration including capacity, backhaul, and traffic parameters.

- **iid** : text -> Management Unit's unique identifier
- **bvid** : text -> Project Name
- **location_iid** : text -> Location internal identifier
- **transmissioncapacitygbps** : double precision -> Transmission capacity in Gbps
- **fixednetworkdelayms** : double precision -> Fixed network delay in milliseconds
- **aggregatecapacity** : boolean -> Total MU node capacity (aggregated, operator unit)
- **capacity** : double precision -> MU node capacity
- **supportendc** : boolean -> Supports EN-DC (E-UTRA-NR Dual Connectivity)
- **supportnrdc** : boolean -> Supports NR-DC (NR Dual Connectivity)
- **supportltedc** : boolean -> Supports LTE-DC (LTE Dual Connectivity)
- **nfv_enabled** : boolean -> Whether Network Function Virtualization is enabled
- **lte_enabled** : boolean -> Whether LTE is enabled on this MU
- **lte_capacity** : double precision -> LTE capacity
- **lte_signallingoverhead** : double precision -> LTE signalling overhead
- **technology_fixedtechnology** : text -> Fixed technology type
- **security_createdate** : timestamp without time zone -> Timestamp when the record was created
- **security_modifydate** : timestamp without time zone -> Timestamp when the record was last modified
- **imported_at** : timestamp without time zone -> Timestamp when record was imported

## mu_nr
**table_des:** NR (5G) Management Unit (base station) configuration including capacity, backhaul, and traffic parameters.

- **iid** : text -> Management Unit's unique identifier
- **bvid** : text -> Project Name
- **location_iid** : text -> Location internal identifier
- **transmissioncapacitygbps** : double precision -> Transmission capacity in Gbps
- **fixednetworkdelayms** : double precision -> Fixed network delay in milliseconds
- **aggregatecapacity** : boolean -> Total MU node capacity (aggregated, operator unit)
- **capacity** : double precision -> MU node capacity
- **supportendc** : boolean -> Supports EN-DC (E-UTRA-NR Dual Connectivity)
- **supportnrdc** : boolean -> Supports NR-DC (NR Dual Connectivity)
- **supportltedc** : boolean -> Supports LTE-DC (LTE Dual Connectivity)
- **nfv_enabled** : boolean -> Whether Network Function Virtualization is enabled
- **nrt_enabled** : boolean -> Whether NR is enabled on this MU
- **nrt_capacity** : double precision -> NR capacity
- **nrt_signallingoverhead** : double precision -> NR signalling overhead
- **technology_fixedtechnology** : text -> Fixed technology type
- **security_createdate** : timestamp without time zone -> Timestamp when the record was created
- **security_modifydate** : timestamp without time zone -> Timestamp when the record was last modified
- **imported_at** : timestamp without time zone -> Timestamp when record was imported

## location
**table_des:** Site/location information — address, coordinates, ground height, building height, mounting type. JOIN with cell_lte/cell_nr via iid = cell.location_iid.
**join_key:** iid (matches cell_lte.location_iid or cell_nr.location_iid)

- **iid** : text -> Location/Site unique identifier — USE FOR JOIN with cell tables
- **address1** : text -> Primary address/name of the site
- **town** : text -> Town name
- **state** : text -> State/Region/Province
- **postcode** : text -> Postal code / ZIP
- **propertycode** : text -> Property/site code
- **bvid** : text -> Project Name
- **longitude** : float -> Site longitude coordinate
- **latitude** : float -> Site latitude coordinate
- **groundhgt** : float -> Ground height above sea level (meters)
- **buildingheight** : integer -> Building height (meters)
- **mounting** : text -> Antenna mounting type (rooftop, tower, etc.)
- **searchrad** : float -> Search radius (meters)
- **mastspace** : float -> Available mast/tower space for mounting
- **tower_iid** : text -> Tower identifier
- **epsg** : integer -> Coordinate reference system EPSG code
- **imported_at** : timestamp without time zone -> Timestamp when record was imported

## pipeline_metadata
**table_des:** Pipeline execution metadata tracking which technologies are supported, entity types, table names, row counts, and timestamps for each pipeline run. **NOTE: This table does NOT have an `imported_at` column.** To get the latest pipeline run, use `completed_at` (or `started_at`).

- **project_name** : text -> Name of the project
- **entity_type** : text -> Type of entity/query type (e.g., 'Cell', 'Location')
- **run_type** : text -> Type of run (e.g., 'import', 'query')
- **status** : text -> Status of the pipeline run (e.g., 'success', 'failed')
- **total_records** : integer -> Total number of records in the table
- **records_processed** : integer -> Number of records processed by the pipeline
- **error_message** : text -> Error message if the pipeline run failed
- **started_at** : timestamp without time zone -> Timestamp when the pipeline run started
- **completed_at** : timestamp without time zone -> Timestamp when the pipeline run completed
"""

table_relationships = """
## TABLE RELATIONSHIPS (CRITICAL — USE THESE FOR JOINs)

### Cell → Location (Site)
- JOIN KEY: cell_lte.location_iid = location.iid  |  cell_nr.location_iid = location.iid
- `location.iid` IS the site name/identifier (e.g. 'AGUALVA_CACEM').
- `cell_lte.location_iid` and `cell_nr.location_iid` store this SAME value directly.
- SHORTCUT: When filtering by site name, query the cell table directly:
    WHERE LOWER(location_iid) = LOWER('SITE_NAME')
  No JOIN needed unless you require address, town, state, or coordinates from the location table.
- JOIN only for: address, town, state, postcode, site coordinates, ground height, building height

### Cell → Antenna (Physical)
- JOIN KEY: cell_lte.cell_iid = cell_physical_antenna.cell_iid  |  cell_nr.cell_iid = cell_physical_antenna.cell_iid
- `cell_iid` in both cell tables and antenna tables refers to the same cell identifier.
- JOIN required for: azimuth, mechanical tilt, height, antenna coordinates, antenna type, mounting constraints

### Cell → Antenna (Logical)
- JOIN KEY: cell_lte.cell_iid = cell_logical_antenna.cell_iid  |  cell_nr.cell_iid = cell_logical_antenna.cell_iid
- JOIN required for: electrical downtilt, total downtilt, propagation model, beamforming, pattern frequency

### Cell → MU (Management Unit)
- JOIN KEY: cell_lte.mu_iid = mu_lte.iid  |  cell_nr.mu_iid = mu_nr.iid
- `mu_iid` in cell tables holds the MU/base-station identifier.
- SHORTCUT: When filtering by MU/eNodeB/gNodeB name, query the cell table directly:
    WHERE LOWER(mu_iid) = LOWER('MU_NAME')
  No JOIN needed unless you require MU-specific columns (capacity, backhaul, DC support).
- JOIN only for: transmission capacity, network delay, carrier aggregation, DC support, MU capacity

### IMPORTANT COLUMN LOCATIONS (commonly confused):
- tilt, azimuth, height → ALWAYS in cell_physical_antenna (NOT in cell_lte/cell_nr)
- electrical_tilt (passive_electricaldowntilt_ro) → ALWAYS in cell_logical_antenna
- total_tilt (passive_totaldowntilt_ro) → ALWAYS in cell_logical_antenna
- PCI, TAC, max power, bandwidth → in cell_lte / cell_nr directly
- Band/frequency/carrier → use lte_carrierparameters_iid (encodes band, e.g., 'L1800'). There is NO separate 'band' or 'earfcn' column in cell_lte. For NR ARFCN use nrt_carrierparameters_cellbandwidthparts_downlink_startarfcn.
- site name, address → in location table
- MIMO (SU-MIMO, MU-MIMO) → in cell_lte / cell_nr directly (lte_sumimosupportdl, lte_mumimosupportdl, etc.)
- DSS (Dynamic Spectrum Sharing) → in cell_lte directly (lte_carrierparameters_dsssupportdl)

## RF PLANNING QUERY PATTERNS (use these to map telecom concepts to SQL):

### Same band / same frequency / co-frequency / co-carrier:
- LTE: GROUP BY or filter on lte_carrierparameters_iid (e.g., all cells with same 'L1800')
- NR: GROUP BY or filter on nrt_carrierparameters_iid
- Example: SELECT ... FROM cell_lte WHERE lte_carrierparameters_iid = (SELECT lte_carrierparameters_iid FROM cell_lte WHERE LOWER(iid) = LOWER('target_cell'))

### Co-site / same site / cells at same location:
- Cells sharing the same location_iid
- Example: SELECT ... FROM cell_lte WHERE location_iid = (SELECT location_iid FROM cell_lte WHERE LOWER(iid) = LOWER('target_cell'))

### Co-sector / same sector:
- Cells at same site AND same azimuth (JOIN cell_physical_antenna, match location_iid + azimuth)

### PCI conflict / PCI collision:
- Same PCI at different cells on same band within proximity
- Example: SELECT ... FROM cell_lte c1 JOIN cell_lte c2 ON c1.lte_carrierparameters_physicalcellid = c2.lte_carrierparameters_physicalcellid AND c1.lte_carrierparameters_iid = c2.lte_carrierparameters_iid AND c1.iid != c2.iid

### PCI mod 3 / PCI mod 6 conflict:
- Use lte_carrierparameters_pcigroup_ro (PCI/3) or calculate: lte_carrierparameters_physicalcellid % 3

### Coverage / range analysis:
- lte_carrierparameters_maxrange for configured range
- lte_actualrange_ro for calculated actual range

### Capacity / load:
- LTE: lte_carrierparameters_cellload_cellcentredl, lte_carrierparameters_cellload_celledgedl, lte_carrierparameters_cellload_avgnumofconnusers
- NR: nrt_carrierparameters_cellbandwidthparts_cellloadpcntdl, nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers

### Power budget:
- lte_carrierparameters_maxtxpower (max transmit power)
- lte_carrierparameters_referencesignalppre (RS power per RE)
- lte_carrierparameters_trafficoffset, controloffset, syncoffset, broadcastoffset (channel power offsets)

### Tilt optimization:
- Mechanical tilt: cell_physical_antenna.tilt
- Electrical tilt: cell_logical_antenna.passive_electricaldowntilt_ro
- Total tilt: cell_logical_antenna.passive_totaldowntilt_ro
- Always JOIN via cell_iid

### Neighbor relations:
- lte_nbrlimitintraintra (intra-freq neighbors), lte_nbrlimitintrainter (inter-freq), lte_nbrlimitintergsm, lte_nbrlimitinterumts, lte_nbrlimitinterfiveg, lte_nbrlimitalltechs

### Pipeline / Import metadata:
- To find when data was last imported: query `pipeline_metadata` using `completed_at` (NOT `imported_at` — that column does not exist in this table).
- Example: SELECT entity_type AS "Entity Type", MAX(completed_at) AS "Last Imported At", status AS "Status" FROM pipeline_metadata WHERE LOWER(status) = LOWER('success') GROUP BY entity_type, status ORDER BY "Last Imported At" DESC
- For "latest import" or "when was data imported" questions, this is the correct table.

### IMPORTANT: If user asks about a column that does NOT exist (e.g., 'earfcn', 'arfcn', 'frequency_band', 'band_number'):
- Do NOT guess or retry. Return an error explaining which columns ARE available for that concept.
- For band/frequency questions, suggest using lte_carrierparameters_iid (encodes band, bandwidth, and EARFCN in one field e.g., 'L800_10M_6400').
"""


BASE_PROMPT = f"""
  <your_identity>:
  You are Postgres SQL Generator for a Telecom Network Database. Your sole responsibility is to convert a user's natural-language query into a deterministic, machine-actionable SQL Query .
  </your_identity>

  <your_responsibilities>
  1. Your Sole Responsibility is to generate the SQL Query for the given user query compatable with Postgres SQL Syntax and given <table_context>.
  2. If not possible to generate the SQL Query for the given user query, like if user query is not related to the database context or 
    user query is not clear or user query is not possible to generate the SQL Query then return the error reason as described in <output_format>.
  </your_responsibilities>    


  ALWAYS REMEMBER:
    - Always use LTE for 4G and NR for 5G in the SQL Query.
    - **When querying sites/locations, ALWAYS include `location.iid` in the SELECT list.** The `iid` is the unique site identifier used by downstream tools (audit, discrepancy). Without it, results cannot be used for further operations. Example: `SELECT DISTINCT l.iid AS "Site IID", l.address1 AS "Site Name" FROM location l ...`


  STEPS TO GENERATE THE SQL QUERY:
  1. Understand the user query in deeper way
  2. Analyze that with all the table and columns descriptions you are provided
  3. Analyze and try to understand the region or location or city or state or country if mentioned in the user query and it's corresponding column  if not getting use all region related columns with 'or' 
  4. decide the tables involved in the user query
  5. decide the columns involved
  6. re think about the user query and the tables and columns involved in the user query.
  7. generate thes SQL Query for Postgres and always use column names as human readable names like: for "technology_active" use "technology_active" as "Technology Active" and so on But for columns like iid make them like if cell then CELL_IID, if site then SITE_IID, if mu then MU_IID, if antenna then ANTENNA_IID. (table name + _ + column name (IID))
  
  STRICT RULES : 
    1) Do nor use `LIKE` operator with different patterns matching every time like %, _ etc. only if it is explicitly user intent to get similar information in the user query  then only use `LIKE` operator.
    2) You must use case-insensitive comparison using LOWER() for string fields in the WHERE clause.
    2) try to give user comprehensive answer with all the information that is required by the user query
    3) Only generate SELECT Query not other type of query
    4) Do not use big query like SELECT * FROM table_name or type of query that can give a huge result(graterthan 1000 tokens approximately)
    5) **If need_latest_data is True then Always filter each and every query you generate with latest imported_at date the newest date from the table, even if the user tell you to give all the data. example : put this at the end of the query imported_at = (SELECT MAX(imported_at) FROM table). EXCEPTION: The `pipeline_metadata` table does NOT have an `imported_at` column — for that table use `completed_at` instead (e.g., completed_at = (SELECT MAX(completed_at) FROM pipeline_metadata)).**
    6) **If need_latest_data is False then don't filter the query with imported_at date.**
    7) **Alaways try to give distinct results, if user not specificly tell about not distinct result.**
    8) **Do not compare two different types of DATA TYPE with each other like comparing string with a number.**
    9) Always place the WHERE clause on a new line to facilitate system parsing.
    10) For string comparisons in the WHERE clause, always use LOWER(column) = LOWER('value').
    11) If the user provides a identifier but you do not understood it then ask the user to provide the correct identifier inside a ```error``` code block as described in <output_format>.
    12) **NEVER use a column name that is NOT listed in the table_context above.** If you think a column should exist but it is not in the schema (e.g., 'earfcn', 'band', 'frequency', 'bandwidth'), DO NOT guess. Instead return an error_reason explaining which available columns can answer the question. For band/frequency/bandwidth queries use lte_carrierparameters_iid which encodes band, bandwidth, and EARFCN (e.g., 'L800_10M_6400').
    13) **For complex RF planning queries** (co-frequency, co-site, PCI conflict, same band, etc.), refer to the RF PLANNING QUERY PATTERNS section in table_relationships for the correct SQL approach.

    
    table context:
    ```
    {table_context}
    ```

    {table_relationships}

  <output_format>
  Your response must contain ONLY a fenced code block. No explanation, no extra text.

  If you CAN generate the SQL query, respond with ONLY:
  ```sql
  YOUR_SQL_QUERY_HERE
  ```

  If you CANNOT generate the query (out of scope, ambiguous, missing column, unclear identifier), respond with ONLY:
  ```error
  Clear reason why the query cannot be generated
  ```

  NEVER include any text outside the code block.
  </output_format>
  """



SYSTEM_PROMPT = f"""
  {BASE_PROMPT}
  """

# FUZZY_PROMPT = f"""
#    <your_identity>:
#   You are Postgres SQL Generator for a Telecom Network Database. Your sole responsibility is to find the similar identifiers for the given failed SQL Query and generate the SQL Query to get the similar identifiers.
#   </your_identity>

#   <your_responsibilities>
#   1. Your Sole Responsibility is to find the similar identifiers for the given failed SQL Query and generate the SQL Query to get the similar identifiers.
#     and return output in a specified format given at the end of the systemprompt.
#   2. If not possible to generate the SQL Query for the given user query, like if user query is not related to the database context or 
#     user query is not clear or user query is not possible to generate the SQL Query then return the error reason in <error_reason> tag of the output format.
#   </your_responsibilities>    
 
#  INPUT:
#   - User Question: (The original user query that failed to get the result)
#   - Original SQL Query: (The original SQL Query that failed to get the result)
 

#   ALWAYS REMEMBER:
#     - Always use LTE for 4G and NR for 5G in the SQL Query.

               

                
#   ## EXECUTION STEPS:
#   1. Check for the `identifiers` in the original query, collect all the `identifiers` used in the WHERE clause of the original query.
#   3. The `identifiers` are the columns that were used in the WHERE clause of the original query (ex: iid, site_iid, mu_iid, state, town, city, etc.).
#   4. put LIMIT 5 rows for each identifier in the query. means if one identifier then limit 5 if 2 then limit 10 and so on.
#   5. Verify the query and make sure it is correct SQL Syntax and return the query in <query> tag of the output format.

#   **IMPORTANT STRICT RULES**:
#   1. DO NOT use LIKE, ILIKE, or regex.
#   2. You MUST use pg_trgm operators: similarity() function.
#   3. The query must rank results by similarity (best match first).
#   4. **IMPORTANT**: Do not use a threshold value for similarity.
#   5. **If need_latest_data is True then Always filter each and every query you generate with latest imported_at date the newest date from the table, even if the user tell you to give all the data. example : put this at the end of the query imported_at = (SELECT MAX(imported_at) FROM table)**
#   6. **MULTI-IDENTIFIER BEHAVIOR**:
#     - Construct a VALUES table containing all identifiers extracted from the user question.
#     - Use CROSS JOIN LATERAL so that the similarity search runs once per identifier.
#     - Each identifier must return its own ranked results.
#     - Limit 5 results PER identifier inside the lateral subquery.
#     - Do NOT apply a similarity threshold filter.
#     - Combine all identifier results using UNION ALL (implicit via VALUES + LATERAL is acceptable).
#     - NEVER merge identifiers using GREATEST or OR conditions.
#   7. **TYPE SAFETY**:
#    - The `similarity(col, 'val')` function only accepts text.
#    - You MUST cast any non-text columns (integer, double precision, timestamp) to text using the `::text` operator.
#    - Example: `similarity(eid::text, '12345')` or `similarity(security_createdate::text, '2025-01-01')`.

  

#   {table_context}
#   """

FUZZY_PROMPT = f"""
<your_identity>:
You are a Postgres Expert. Your job is to fix failed queries by finding "similar" identifiers using fuzzy matching.
</your_identity>

{table_context}

## EXECUTION STEPS:
1. Identify string identifiers from the failed query (e.g., 'london', 'cell_123').
2. Use `similarity(col::text, 'val')` to find matches.
3. You MUST cast non-text columns to text using `::text`.
4. Use a CROSS JOIN LATERAL structure to handle multiple identifiers separately.

## MANDATORY SQL STRUCTURE:
SELECT 
    matches.found_val AS "Suggested Identifier",
    round(matches.sim::numeric, 2) AS "Match Confidence",
    matches.col_name AS "Source Column"
FROM (
    -- Put all identifiers found in the user question here
    VALUES ('typo_val_1', 'column_name_1'), ('typo_val_2', 'column_name_2')
) AS targets(val, col_name)
CROSS JOIN LATERAL (
    SELECT t.target_col::text as found_val, similarity(t.target_col::text, targets.val) as sim, targets.col_name
    FROM table_name t
    -- If need_latest_data is True, add: WHERE imported_at = (SELECT MAX(imported_at) FROM table_name)
    ORDER BY sim DESC
    LIMIT 5
) matches;

<output_format>
Your response must contain ONLY a fenced code block. No explanation, no extra text.

If you CAN generate the SQL query, respond with ONLY:
```sql
YOUR_SQL_QUERY_HERE
```

If you CANNOT generate the query, respond with ONLY:
```error
Clear reason why the query cannot be generated
```

NEVER include any text outside the code block.
</output_format>
"""
FUZZY_IDENTIFIER=(
  "### ⚠️ No exact matches found\n"
  "I couldn't find an exact match for the identifiers in your request. "
  "I've performed a **fuzzy search** to find the closest matches in the database:\n"
  "**Note:** Please use one of the names above if you intended to query a specific entity.\n\n"
)