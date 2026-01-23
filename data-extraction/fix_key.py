
import json

# Read the file directly
with open('/tmp/google_sa_key.json', 'r') as f:
    content = f.read()

# It seems the previous cat output showed it was valid JSON structure but had newlines
# in the private_key field which might have been garbled by the echo/base64 process.
# We will try to parse it. If it fails, we will manually fix the newlines.

try:
    data = json.loads(content)
    # Ensure private key has correct newlines
    pk = data.get('private_key', '')
    if '-----BEGIN PRIVATE KEY-----' in pk:
        # It looks like the key is there. 
        # Sometimes \\n literals are needed instead of actual newlines for gcloud json
        # OR actual newlines.
        # Let's write it back cleanly.
        with open('/tmp/google_sa_key_fixed.json', 'w') as f:
            json.dump(data, f, indent=2)
            print("Fixed JSON saved.")
    else:
        print("Private key header not found.")
except json.JSONDecodeError as e:
    print(f"JSON Error: {e}")
    # If it failed to parse, it might be due to unescaped control characters
    # We can try to fix strictly the newlines
    fixed_content = content.replace('\n', '\\n')
    # But wait, the file usually HAS newlines between fields.
    print("Manual fix required based on specific corruption.")
