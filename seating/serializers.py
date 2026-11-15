from rest_framework import serializers


class GroupRequestSerializer(serializers.Serializer):
    table = serializers.IntegerField(min_value=1)
    persons = serializers.IntegerField(min_value=1)
#why we use serializers.Serializer instead of serializers.ModelSerializer in this case is because we are not directly mapping to a model. Instead, we are validating input data for creating a customer group, which may not correspond to a single model instance. Using serializers.Serializer allows us to define custom validation and processing logic for the incoming request data.
#why we use min_value=1 for both fields is to ensure that the input values for table number and number of persons are positive integers. A table number or a group size of zero or negative would not make sense in the context of a restaurant seating system, so we enforce this constraint at the serializer level to prevent invalid data from being processed further.
#why we use serializers.IntegerField for both fields is because we expect the input data for both the table number and the number of persons to be whole numbers. IntegerField is appropriate for these cases as it validates that the input is an integer and allows us to specify additional constraints, such as minimum values, to ensure the data meets our requirements.