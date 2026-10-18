import { networkInterfaces } from 'node:os';

const addresses = Object.entries(networkInterfaces())
  .filter(([name]) => !/vEthernet|VMware|VirtualBox|WSL|docker|loopback/i.test(name))
  .flatMap(([, entries]) => entries)
  .filter(entry => entry.family === 'IPv4' && !entry.internal && !entry.address.startsWith('169.254.'));

export const localHost = process.env.STUPROJECT_HOST || addresses[0]?.address || '127.0.0.1';
export const frontendPort = Number(process.env.STUPROJECT_PORT || 5173);
export const localOrigin = `http://${localHost}:${frontendPort}`;
