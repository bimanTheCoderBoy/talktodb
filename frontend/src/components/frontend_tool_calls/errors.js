export class FrontendConnectorError extends Error {
  constructor(message) {
    super(message);
    this.name = "FrontendConnectorError";
  }
}
