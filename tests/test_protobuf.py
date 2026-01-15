from core.protobuf_decoder import ProtobufDecoder

proto_file = r"C:\Testing\proto_decoder\protobuf-samples\Dish5gFcaps.proto"
ptbf_file = r"C:\Testing\proto_decoder\protobuf-samples\CfCcStats.protobuf"

decoder = ProtobufDecoder(proto_file, verbose=True)

# Check if CfCcStats is recognized
print("Is CfCcStats a message?", decoder.schema_parser.is_message_type('CfCcStats'))

# Get the message
msg = decoder.schema_parser.find_message_type('CfCcStats')
print("CfCcStats message:", msg)
if msg:
    print("Fields:", msg.fields)

# Decode
result = decoder.decode_and_map(
    ptbf_file,
    'XcipioMetrics',
    'output_test.json'
)

print("Result:", result)
