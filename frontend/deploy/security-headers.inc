add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "same-origin" always;
# connect-src: 'self' = this site (what the UI uses). https://*.cloudshell.dev is added for Google Cloud Shell Web
# Preview: its proxy can answer an XHR with a redirect to another *.cloudshell.dev host, and the browser checks the
# redirect target against connect-src too. Deliberately NOT "https:" (that would let injected script call any server).
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https://*.cloudshell.dev; frame-ancestors 'none'" always;
