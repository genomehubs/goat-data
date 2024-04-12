Feature: Testing initialise_organelle_info function

  Scenario Outline: Testing initialise_organelle_info function with different scenarios
    Given a data dictionary <data>
    And the name of the organelle <organelle_name>
    When initialise_organelle_info is called
    Then the data dictionary should be updated to <expected>

    Examples:
      | data                                                         | organelle_name | expected                                                             |
      | {"processedOrganelleInfo": {}}                               | mitochondrion  | {"processedOrganelleInfo": {"mitochondrion": {}}}                    |
      | {"processedOrganelleInfo": {"mitochondrion": {}}}            | chloroplast    | {"processedOrganelleInfo": {"mitochondrion": {}, "chloroplast": {}}} |
      | {}                                                           | mitochondrion  | {"processedOrganelleInfo": {"mitochondrion": {}}}                    |
      | {"processedOrganelleInfo": {"mitochondrion": {"gene": 123}}} | mitochondrion  | {"processedOrganelleInfo": {"mitochondrion": {"gene": 123}}}         |
