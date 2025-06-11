from embedchain.models.data_type import (
    DataType,
    DirectDataType,
    IndirectDataType,
    SpecialDataType,
)


def test_subclass_types_in_data_type():
    """Test that all data type category subclasses are contained in the composite data type"""
    # Check if DirectDataType values are in DataType
    for data_type in DirectDataType:
        assert data_type.value in DataType._value2member_map_

    # Check if IndirectDataType values are in DataType
    for data_type in IndirectDataType:
        assert data_type.value in DataType._value2member_map_

    # Check if SpecialDataType values are in DataType
    for data_type in SpecialDataType:
        assert data_type.value in DataType._value2member_map_


def test_data_type_in_subclasses():
    """Test that all data types in the composite data type are categorized in a subclass"""
    for data_type in DataType:
        if data_type.value in DirectDataType._value2member_map_:
            assert data_type.value in DirectDataType._value2member_map_
        elif data_type.value in IndirectDataType._value2member_map_:
            assert data_type.value in IndirectDataType._value2member_map_
        elif data_type.value in SpecialDataType._value2member_map_:
            assert data_type.value in SpecialDataType._value2member_map_
        else:
            assert False, f"{data_type.value} not found in any subclass enums"
