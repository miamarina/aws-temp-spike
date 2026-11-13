# Spike policy templates

These JSON files are extracted unchanged from the [tested code appendix](../04-code.md). They are templates for the implemented spike, with explicit placeholder resource names:

- [bucket-policy.json](bucket-policy.json): deny non-TLS S3 access; this does not grant public access.
- [lambda-trust-policy.json](lambda-trust-policy.json): allow the Lambda service to assume the execution role.
- [lambda-permissions-policy.json](lambda-permissions-policy.json): read the fixture/saved bullets, write output/attempt markers, and write to the exact pre-created log group.

Replace `YOUR_BUCKET`, `YOUR_PROJECT_ID` and `YOUR_FUNCTION_NAME` only for an authorized deployment. Keep Regional resources in `eu-north-1`. These policies do not create the bucket, role, log group or function and are not permissions for the planned full application.
