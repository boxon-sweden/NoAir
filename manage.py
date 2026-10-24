"""Local setup, startup and retention commands. Never use real data in demo mode."""
from __future__ import annotations
import argparse
import getpass
import os
import secrets
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description='Noair pilot administration')
    parser.add_argument('command',choices=['setup','run','purge','password-hash'])
    args=parser.parse_args()
    if args.command in ('setup','password-hash'):
        from argon2 import PasswordHasher
        if args.command=='setup' and (ROOT/'.env').exists():
            raise SystemExit('.env already exists; edit it explicitly or use password-hash. Nothing overwritten.')
        password=getpass.getpass('Choose admin password (minimum 14 characters): ')
        if len(password)<14:
            raise SystemExit('Use at least 14 characters.')
        if password!=getpass.getpass('Repeat password: '):
            raise SystemExit('Passwords differ.')
        password_hash=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2).hash(password)
        if args.command=='password-hash':
            print(password_hash)
            return
        content=f'APP_ENV=development\nPUBLIC_ORIGIN=http://127.0.0.1:8000\nSECRET_KEY={secrets.token_urlsafe(48)}\nADMIN_USERNAME=admin\nADMIN_PASSWORD_HASH={password_hash}\nSUBMISSIONS_ENABLED=1\nPRIVACY_REVIEWED=0\nRETENTION_DAYS=180\n'
        path=ROOT/'.env'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(content)
        print('Local test configuration created. Test data only. Run: python manage.py run')
    else:
        from app import create_app,config_from_env,purge
        if args.command=='purge':
            config=config_from_env();create_app(config);print(f'Removed {purge(config)} expired reports.')
        else:
            import uvicorn
            uvicorn.run(create_app(),host='127.0.0.1',port=8000,access_log=False,proxy_headers=False)

if __name__=='__main__':main()
