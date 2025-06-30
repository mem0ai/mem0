const readline = require('readline');
const http = require('http');
const https = require('https');
const url = require('url');

const remoteUrlString = process.argv[2];
if (!remoteUrlString) {
    console.error("Fatal: Remote URL was not provided.");
    process.exit(1);
}

const remoteUrl = new URL(remoteUrlString);
const transport = remoteUrl.protocol === 'https:' ? https : http;

const rl = readline.createInterface({
    input: process.stdin,
    terminal: false
});

const sendError = (id, message) => {
    const errorResponse = {
        jsonrpc: "2.0",
        error: { code: -32603, message: `Proxy Error: ${message}` },
        id: id || null,
    };
    process.stdout.write(JSON.stringify(errorResponse));
};

rl.on('line', (line) => {
    let requestBody;
    try {
        requestBody = JSON.parse(line);
    } catch (e) {
        sendError(null, 'Failed to parse incoming JSON from client.');
        return;
    }

    const options = {
        hostname: remoteUrl.hostname,
        port: remoteUrl.port || (remoteUrl.protocol === 'https:' ? 443 : 80),
        path: remoteUrl.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(line),
            'Accept': 'application/json'
        }
    };

    const req = transport.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => {
            data += chunk;
        });
        res.on('end', () => {
            process.stdout.write(data);
        });
    });

    req.on('error', (e) => {
        console.error(`Request to remote failed: ${e.message}`);
        sendError(requestBody.id, e.message);
    });

    req.write(line);
    req.end();
});

rl.on('close', () => {
    process.exit(0);
}); 