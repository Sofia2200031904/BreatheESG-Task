# Sources and Real-World Basis

This demo uses public guidance and product documentation to shape realistic source data and ESG review behavior.

- SAP Help Portal, file import formats: SAP documentation describes importing consolidation records from CSV or Office Open XML files and illustrates enterprise-style field constraints such as plant-specific material data and unit-of-measure codes. This informed the SAP flat-file export simulation with plant codes, procurement categories, dates, quantities, and units.  
  https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/6d52de87aa0d4fb6a90924720a5b0549/82d9dd5336a140c5b967bfcaf1ff90cc.html

- EPA Scope 1 and Scope 2 Inventory Guidance: EPA defines Scope 1 as direct emissions from owned or controlled sources and Scope 2 as indirect emissions from purchased electricity, steam, heat, or cooling. This informed the scope mapping for fuel combustion and utility electricity.  
  https://www.epa.gov/climateleadership/scope-1-and-scope-2-inventory-guidance

- GHG Protocol Scope 3 FAQ and Scope 3 Standard resources: GHG Protocol resources organize Scope 3 emissions and include data collection, data quality, and category guidance. This informed procurement and business travel as Scope 3 activity data.  
  https://ghgprotocol.org/scope-3-frequently-asked-questions-0  
  https://ghgprotocol.org/standards/scope-3-standard

- SAP Concur Travel reports documentation: Concur travel reporting includes ticket purchases, hotel accommodations, policy exceptions, date ranges, itinerary sources, and export/display formats. This informed the corporate travel CSV shape.  
  https://help.sap.com/docs/CONCUR_TRAVEL/5dbd7ec342a642bc9341b3f8318d3ac7/726764d66da81014a6a9a7500609a9b7.html

- GHG Protocol Scope 3 Category 6 technical guidance: Business travel guidance includes transportation and optional hotel-night collection approaches. This informed flights, rail, taxi, and hotel stay categories.  
  https://ghgprotocol.org/sites/default/files/standards_supporting/Chapter6.pdf

- IATA CO2 Connect and ICAO Carbon Emissions Calculator pages: Aviation references emphasize airport/route-specific data and flight emissions calculation. This informed airport-code based distance estimation for missing flight distances.  
  https://www.iata.org/en/services/statistics/intelligence/co2-connect/  
  https://www.icao.int/environmental-protection/CarbonOffset/Pages/default.aspx

- EPA Greenhouse Gas Equivalencies Calculator revision history: EPA notes use of eGRID emission rates and electricity input changes. This informed the simplified electricity factor placeholder and the warning that real deployments should use region and year-specific factors.  
  https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-revision-history
