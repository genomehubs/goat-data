Feature: parse ncbi datasets

    Scenario Outline: we set an organelle name
        Given a sequence record has location <location>
        When we set the organelle name
        Then the name will be <name>
      Examples: Organelles
        | location      | name          |
        | Mitochondrion | mitochondrion |
        | mitochondrion | mitochondrion |
        | Chloroplast   | plastid       |
        | chloroplast   | plastid       |
        | Apicoplast    | plastid       |
    
    Scenario: we set an organelle name with no location
        Given a sequence record has no location
        When we set the organelle name
        Then the name will not be set
    
    Scenario Outline: we can check if a sequence is chromosomal
        Given a sequence record has role <role>
        When we check if it is chromosomal
        Then the result will be <value>
      Examples: Roles
        | role               | value |
        | assembled-molecule | True  |
        | unplaced-scaffold  | False |
        