Feature: Testing set_additional_organelle_values function

  Scenario Outline: Testing set_additional_organelle_values function with different scenarios
    Given a sequence data <seq>
    And an organelle dictionary <organelle>
    And a data dictionary <data>
    And the name of the organelle <organelle_name>
    And the assembled molecule flag is <is_assembled>
    When set_additional_organelle_values is called
    Then the data dictionary should be updated to <expected>

    Examples:
      | seq                                                                    | organelle | data                                              | organelle_name | is_assembled | expected                                                                                                         |
      | [{"genbank_accession": "ABC123", "length": 10000, "gc_percent": 40.5}] | {}        | {"processedOrganelleInfo": {"mitochondrion": {}}} | mitochondrion  | True         | {"processedOrganelleInfo": {"mitochondrion": {"assemblySpan": 10000, "gcPercent": 40.5, "accession": "ABC123"}}} |
      | [{"genbank_accession": "DEF456"}, {"genbank_accession": "GHI789"}]     | {}        | {"processedOrganelleInfo": {"chloroplast": {}}}   | chloroplast    | False        | {"processedOrganelleInfo": {"chloroplast": {"scaffolds": "DEF456;GHI789"}}}                                      |
      | []                                                                     | {}        | {"processedOrganelleInfo": {"plastid": {}}}       | plastid        | False        | {"processedOrganelleInfo": {"plastid": {"scaffolds": ""}}}                                                       |
