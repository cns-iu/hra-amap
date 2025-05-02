from enum import Enum


class ConfigKeys(str, Enum):
    CREATION_DATE = "creation_date"
    DONOR_DATA_KEY = "donor"
    ID = "id"
    AT_ID = "@id"
    INPUT_FILES = "input_files"
    RUI_LOCATION_KEY = "rui_location"
    SOURCE = "source"
    TARGET = "target"
    TARGET_NAME = "target_name"
    LABEL = "label"
    LINK = "link"
    PLACEMENT = "placement"
    PLACEMENT_DATE = "placement_date"
    RIGID_REGISTRATION = "rigid_registration"
    NONRIGID_REGISTRATION = "nonrigid_registration"
