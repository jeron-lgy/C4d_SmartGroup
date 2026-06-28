CONTAINER Tsmartgroupnulltag
{
    NAME Tsmartgroupnulltag;
    INCLUDE Texpression;

    GROUP ID_TAGPROPERTIES
    {
        BOOL SGN_TAG_ENABLE { }
        BOOL SGN_TAG_SHOW_BOX { }
        COLOR SGN_TAG_BOX_COLOR { }
        REAL SGN_TAG_PADDING
        {
            UNIT METER;
            MIN 0.0;
            STEP 1.0;
        }
    }
}
