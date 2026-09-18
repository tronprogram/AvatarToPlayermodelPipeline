player_manager.AddValidModel("[[ display_name ]]", "[[ model_path ]]")
[% if hands_path %]
player_manager.AddValidHands("[[ display_name ]]", "[[ hands_path ]]", 0, "00000000")
[% endif %]
