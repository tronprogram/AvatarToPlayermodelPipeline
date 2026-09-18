"""Standard 15-capsule Source/GMod playermodel collision bones."""

from __future__ import annotations

# (bone name, radius as a fraction of bone length)
RAGDOLL_CAPSULES: tuple[tuple[str, float], ...] = (
    ("ValveBiped.Bip01_Head1", 0.55),
    ("ValveBiped.Bip01_Spine2", 0.45),
    ("ValveBiped.Bip01_Pelvis", 0.40),
    ("ValveBiped.Bip01_L_UpperArm", 0.22),
    ("ValveBiped.Bip01_L_Forearm", 0.20),
    ("ValveBiped.Bip01_L_Hand", 0.35),
    ("ValveBiped.Bip01_R_UpperArm", 0.22),
    ("ValveBiped.Bip01_R_Forearm", 0.20),
    ("ValveBiped.Bip01_R_Hand", 0.35),
    ("ValveBiped.Bip01_L_Thigh", 0.22),
    ("ValveBiped.Bip01_L_Calf", 0.20),
    ("ValveBiped.Bip01_L_Foot", 0.35),
    ("ValveBiped.Bip01_R_Thigh", 0.22),
    ("ValveBiped.Bip01_R_Calf", 0.20),
    ("ValveBiped.Bip01_R_Foot", 0.35),
)
