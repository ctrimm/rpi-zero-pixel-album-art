# Admin Panel

The Admin Panel provides a secure web interface for managing and updating your LED Matrix Display configuration in real-time, without needing to SSH into the device or restart the application.

## Features

- **🔐 Secure Authentication**: Password-protected access to configuration
- **📝 Live Config Editor**: Edit configuration JSON directly in your browser
- **✓ Validation**: Validate configuration before saving to prevent errors
- **💾 Live Updates**: Changes apply immediately without restarting the application
- **📊 System Status**: View current display status and settings
- **✨ JSON Formatting**: Auto-format JSON for better readability

## Setup

### 1. Configure Admin Credentials

Edit your `config.json` file to set admin credentials:

```json
{
  "web_server": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false,
    "admin_username": "admin",
    "admin_password": "your-secure-password-here",
    "secret_key": "generate-a-random-string-here"
  }
}
```

**Security Recommendations:**

1. **Change the default password** from "changeme" to something secure
2. **Generate a random secret key** - use this command:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
3. **Use HTTPS** in production (consider using nginx reverse proxy with SSL)
4. **Limit network access** - if running on local network only, set `host` to `127.0.0.1`

### 2. Restart the Application

After updating credentials, restart the application:

```bash
# If running as a service
sudo systemctl restart spotify-display

# If running manually
# Stop the application (Ctrl+C) and restart
python3 src/main.py
```

## Accessing the Admin Panel

### From Browser

1. **Login Page**: Navigate to `http://<your-pi-ip>:5000/login`
2. **Enter credentials**: Use the username and password from your config
3. **Access Admin Panel**: After login, you'll be redirected to the admin panel

### Default Credentials

**⚠️ IMPORTANT: Change these immediately after first login!**

- Username: `admin`
- Password: `changeme`

## Using the Admin Panel

### Configuration Editor

The main editor allows you to modify the entire configuration JSON:

**Features:**
- **Syntax highlighting** through monospace font
- **Line numbers** for easy reference
- **Validation** before saving
- **Format JSON** button to clean up formatting
- **Reload** to discard changes and reload from file

**Workflow:**

1. **Edit** the configuration in the text editor
2. **Validate** your changes (optional but recommended)
3. **Save** to apply changes immediately
4. Changes take effect **without restarting** the application

### System Status

View real-time system information:

- Current display mode
- Brightness level
- Spotify playback status
- Available display modes

## Configuration Changes

### What Updates Immediately

These settings apply instantly when saved:

✅ **Display brightness**
✅ **Default display mode** (switches mode immediately)
✅ **Mode schedules**
✅ **Web server settings** (except port)
✅ **Weather/Sports settings**
✅ **Image processing settings**

### What Requires Restart

Some settings require an application restart:

⚠️ **Spotify API credentials** (client_id, client_secret)
⚠️ **Display hardware settings** (rows, cols, GPIO settings)
⚠️ **Web server port**
⚠️ **Admin credentials** (take effect after restart)

## Security Best Practices

### Production Deployment

For production use, implement these security measures:

1. **Use Strong Passwords**
   ```bash
   # Generate a random password
   openssl rand -base64 32
   ```

2. **Use HTTPS with Reverse Proxy**

   Example nginx configuration:
   ```nginx
   server {
       listen 443 ssl;
       server_name your-domain.com;

       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Restrict Network Access**

   If only local access needed, bind to localhost:
   ```json
   {
     "web_server": {
       "host": "127.0.0.1",
       "port": 5000
     }
   }
   ```

4. **Use Firewall Rules**
   ```bash
   # Only allow from local network
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   ```

5. **Regular Password Rotation**
   - Change admin password every 90 days
   - Update secret_key periodically

### Development vs Production

**Development:**
```json
{
  "web_server": {
    "host": "127.0.0.1",
    "port": 5000,
    "debug": true,
    "admin_password": "dev-password"
  }
}
```

**Production:**
```json
{
  "web_server": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false,
    "admin_password": "strong-random-password-here",
    "secret_key": "long-random-hex-string-here"
  }
}
```

## API Endpoints

The admin panel uses these API endpoints:

### Authentication

**Login**
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

**Logout**
```bash
POST /api/auth/logout
```

**Check Auth Status**
```bash
GET /api/auth/check
```

### Configuration Management

**Get Configuration** (requires authentication)
```bash
GET /api/admin/config
```

**Update Configuration** (requires authentication)
```bash
POST /api/admin/config
Content-Type: application/json

{
  "spotify": { ... },
  "display": { ... },
  ...
}
```

**Validate Configuration** (requires authentication)
```bash
POST /api/admin/config/validate
Content-Type: application/json

{
  "spotify": { ... },
  "display": { ... },
  ...
}
```

## Troubleshooting

### Can't Access Login Page

**Problem**: Browser shows "Connection refused" or "Cannot connect"

**Solutions:**
1. Verify application is running: `sudo systemctl status spotify-display`
2. Check port: `netstat -tulpn | grep 5000`
3. Verify host setting in config.json (use `0.0.0.0` for network access)
4. Check firewall: `sudo ufw status`

### Login Fails with Correct Credentials

**Problem**: "Invalid credentials" error despite correct password

**Solutions:**
1. Check config.json has correct `admin_username` and `admin_password`
2. Restart application after changing credentials
3. Check logs for errors: `sudo journalctl -u spotify-display -f`
4. Verify no special characters causing JSON parse issues

### Configuration Won't Save

**Problem**: "Failed to save configuration" error

**Solutions:**
1. Check JSON syntax with "Validate" button first
2. Verify file permissions: `ls -la config.json`
3. Check disk space: `df -h`
4. Review validation errors shown in the UI
5. Check application logs for specific errors

### Changes Don't Apply

**Problem**: Configuration saved but changes not visible

**Solutions:**
1. Some settings require restart (see "What Requires Restart" section)
2. Refresh the browser page
3. Check if the changed setting is currently being used
4. Restart application if needed: `sudo systemctl restart spotify-display`

### Session Expires Immediately

**Problem**: Logged out right after login

**Solutions:**
1. Verify `secret_key` is set in config.json
2. Check browser cookies are enabled
3. Ensure system time is correct: `date`
4. Try a different browser

## Development

### Testing Locally

Run the emulator with admin panel enabled:

```bash
# Mac/Linux
source venv/bin/activate
LED_SIMULATOR=1 python3 src/main.py

# Access at http://localhost:5000/admin
```

### Custom Validations

To add custom configuration validation, edit `src/utils/config_manager.py`:

```python
def validate_config(self, config):
    errors = []

    # Add your custom validation
    if 'my_section' in config:
        if config['my_section']['my_value'] < 0:
            errors.append("my_section.my_value must be positive")

    return (len(errors) == 0, errors)
```

## Tips & Tricks

### Quick Config Backup

Before making major changes, copy your config:
```bash
cp config.json config.backup.json
```

### JSON Validation

Test JSON validity before saving:
```bash
cat config.json | python3 -m json.tool
```

### Remote Access via SSH Tunnel

Access admin panel securely over SSH:
```bash
# On your local machine
ssh -L 5000:localhost:5000 pi@raspberrypi.local

# Access at http://localhost:5000/admin
```

### Bulk Configuration Changes

For multiple devices, you can:
1. Edit config on one device via admin panel
2. Export via API: `curl http://pi1:5000/api/admin/config > config.json`
3. Import to other devices: `curl -X POST http://pi2:5000/api/admin/config -d @config.json`

### Mobile Access

The admin panel is mobile-responsive! Access from your phone by navigating to the Pi's IP address.

## Future Enhancements

Planned features for future releases:

- [ ] Multi-user support with roles (admin, viewer)
- [ ] Configuration history and rollback
- [ ] Visual form-based editor (alternative to JSON)
- [ ] Two-factor authentication
- [ ] API key authentication for programmatic access
- [ ] Configuration templates and presets
- [ ] Backup and restore functionality

## Support

For issues or questions:
- Check logs: `sudo journalctl -u spotify-display -f`
- Review [troubleshooting section](#troubleshooting)
- Open an issue on GitHub

## Security Disclosure

If you discover a security vulnerability, please email security@yourdomain.com instead of opening a public issue.
