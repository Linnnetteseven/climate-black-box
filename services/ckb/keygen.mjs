#!/usr/bin/env node
/**
 * Generate a CKB testnet signer and print its address.
 *
 * The private key is written to stdout ONCE and never stored by this script.
 * Put it in .env as CKB_SIGNER_PRIVATE_KEY, which is gitignored. It is a
 * testnet key holding testnet CKB -- worthless -- but the habit matters:
 * a key that touches a log or a repo is a key that is burned.
 */
import { ClientPublicTestnet, SignerCkbPrivateKey } from "@ckb-ccc/core";
import { randomBytes } from "node:crypto";

const privateKey = "0x" + randomBytes(32).toString("hex");
const client = new ClientPublicTestnet();
const signer = new SignerCkbPrivateKey(client, privateKey);
const address = await signer.getRecommendedAddress();

console.log(JSON.stringify({ network: "ckb-testnet", address, privateKey }, null, 2));
