from agent.security.keychain import set_device_token

def main():
    token = input("Paste DEVICE TOKEN from backend admin: ").strip()
    if not token:
        print("No token provided. Aborting.")
        return

    set_device_token(token)
    print("Device token stored securely in Keychain.")

if __name__ == "__main__":
    main()
