"""One-time trusted-PC provisioning. Only ciphertext crosses ADB; never print secrets."""
import argparse, base64, json, os, subprocess
import keyring
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from bluey.project_tracker import sheet_url

parser=argparse.ArgumentParser()
parser.add_argument('--adb',required=True)
parser.add_argument('--serial',required=True)
args=parser.parse_args()
adb=[args.adb,'-s',args.serial]
public=subprocess.check_output(adb+['exec-out','run-as','co.visionairy.bluey','cat','files/phone-public-key.txt'])
key=keyring.get_password('Bluey','openai')
if not key: raise SystemExit('No saved OpenAI key. Save it in Bluey on this trusted PC first.')
google=keyring.get_password('Bluey.ProjectTracker','google-oauth')
payload=json.dumps({'openai_key':key,'google_oauth':json.loads(google) if google else {},'sheet_url':sheet_url()}).encode()
aes_key=AESGCM.generate_key(bit_length=256); nonce=os.urandom(12)
pub=serialization.load_der_public_key(base64.b64decode(public))
wrapped=pub.encrypt(aes_key,padding.OAEP(mgf=padding.MGF1(hashes.SHA1()),algorithm=hashes.SHA256(),label=None))
envelope=json.dumps({k:base64.b64encode(v).decode() for k,v in {
    'wrapped_key':wrapped,'nonce':nonce,'ciphertext':AESGCM(aes_key).encrypt(nonce,payload,None)}.items()}).encode()
subprocess.run(adb+['shell',"run-as co.visionairy.bluey sh -c 'cat > files/phone-profile.pending'"],input=envelope,check=True,stdout=subprocess.DEVNULL)
print('Encrypted profile prepared on phone. Activate it in Bluey Phone settings.')
