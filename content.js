// This script will be injected into the Dhan positions page.
// It will add the "Initiate", "Roll Up", and "Roll Down" buttons
// and implement the corresponding trading logic.

console.log("Dhan Trading Helper content script loaded.");

// --- STATE MANAGEMENT ---
// State to hold the strikes managed by the extension
let initiatedStrikes = [];
const STRIKE_DIFFERENCE = 50; // For NIFTY
// Global cache for the instrument list
let instrumentMaster = null;


// --- CORE FUNCTIONS ---

// Function to get authentication details from localStorage
function getAuthDetails() {
  const accessToken = localStorage.getItem("JWTtoken");
  const dhanClientId = localStorage.getItem("loginId");

  if (!accessToken || !dhanClientId) {
    console.error("Could not find access token or client ID in localStorage.");
    alert("Error: Could not find authentication details. Please ensure you are logged in.");
    return null;
  }
  return { accessToken, dhanClientId };
}

// Function to find the ATM strike price from the page
function findAtmStrike() {
  const priceContainer = document.querySelector(".right_container");
  if (priceContainer && priceContainer.innerText) {
    const priceText = priceContainer.innerText.match(/[\d,.]+/);
    if (priceText) {
      const price = parseFloat(priceText[0].replace(/,/g, ''));
      if (!isNaN(price)) {
        const roundedPrice = Math.round(price / 50) * 50;
        console.log(`Found price: ${price}, rounded to ATM strike: ${roundedPrice}`);
        return roundedPrice;
      }
    }
  }
  console.error("Could not find or parse the price from the '.right_container' element.");
  alert("Error: Could not determine the ATM strike price.");
  return null;
}


// --- INSTRUMENT AND ORDER LOGIC ---

// Function to fetch and parse the instrument master CSV
async function fetchInstrumentMaster() {
  if (instrumentMaster) return instrumentMaster;
  try {
    console.log("Fetching instrument master list...");
    const response = await fetch("https://images.dhan.co/api-data/api-scrip-master.csv");
    const csvText = await response.text();
    const lines = csvText.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    const data = lines.slice(1).map(line => {
      const values = line.split(',').map(v => v.trim());
      return headers.reduce((obj, header, index) => {
        obj[header] = values[index];
        return obj;
      }, {});
    });
    instrumentMaster = data.filter(d => d.SEM_EXM_EXCH_ID === 'NSE' && d.SEM_SEGMENT === 'D');
    console.log(`Instrument master loaded. Found ${instrumentMaster.length} NSE F&O instruments.`);
    return instrumentMaster;
  } catch (error) {
    console.error("Failed to fetch or parse instrument master:", error);
    alert("Critical Error: Could not load the list of instruments from Dhan.");
    return null;
  }
}

// Function to find the nearest weekly expiry date (Thursday)
function getNearestWeeklyExpiry() {
    const today = new Date();
    let expiryDate = new Date(today);
    const dayOfWeek = today.getDay(); // 0=Sun, 4=Thu
    let daysUntilThursday = (4 - dayOfWeek + 7) % 7;
    if (daysUntilThursday === 0 && today.getHours() > 16) { // If it's Thursday past market hours
        daysUntilThursday = 7;
    }
    expiryDate.setDate(today.getDate() + daysUntilThursday);
    const year = expiryDate.getFullYear();
    const month = String(expiryDate.getMonth() + 1).padStart(2, '0');
    const day = String(expiryDate.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Function to get the security ID for a given instrument
async function getSecurityId(strike, optionType) {
  const instruments = await fetchInstrumentMaster();
  if (!instruments) return null;

  const expiryDate = getNearestWeeklyExpiry();
  const matchingInstrument = instruments.find(inst =>
    inst.SEM_INSTRUMENT_NAME === 'OPTIDX' &&
    inst.SEM_UNDERLYING_SYMBOL === 'NIFTY' &&
    inst.SEM_EXPIRY_DATE === expiryDate &&
    inst.SEM_STRIKE_PRICE == strike &&
    inst.SEM_OPTION_TYPE === optionType
  );

  if (matchingInstrument) {
    // The CSV column is 'SEM_SECURITY_ID'
    console.log(`Found securityId: ${matchingInstrument.SEM_SECURITY_ID} for ${strike} ${optionType}`);
    return matchingInstrument.SEM_SECURITY_ID;
  }
  console.error(`Could not find securityId for NIFTY ${strike} ${optionType} with expiry ${expiryDate}`);
  alert(`Error: Could not find a tradable instrument for NIFTY ${strike} ${optionType} with expiry ${expiryDate}.`);
  return null;
}

// Function to execute a single order using the Dhan API
async function executeOrder(order, transactionType = "SELL") {
  const auth = getAuthDetails();
  if (!auth) return;

  const securityId = await getSecurityId(order.strike, order.optionType);
  if (!securityId) return;

  const payload = {
    dhanClientId: auth.dhanClientId,
    transactionType: transactionType,
    exchangeSegment: "NSE_FNO",
    productType: "INTRADAY",
    orderType: "MARKET",
    validity: "DAY",
    securityId: securityId,
    quantity: 50, // This can be configured if needed
  };

  console.log(`Executing ${transactionType} order with payload:`, payload);
  try {
    const response = await fetch('https://api.dhan.co/v2/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'access-token': auth.accessToken },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (response.ok) {
      console.log(`Order placed successfully for ${order.strike} ${order.optionType}. Order ID: ${result.orderId}`);
    } else {
      console.error(`Failed to place order for ${order.strike} ${order.optionType}.`, result);
      alert(`Error placing order for ${order.strike} ${optionType}: ${result.errorMessage}`);
    }
  } catch (error) {
    console.error(`An error occurred while placing order:`, error);
    alert(`A network error occurred while placing the order.`);
  }
}


// --- BUTTON ACTIONS AND PAGE INTERACTION ---

// Function to handle the "Initiate" button click
async function initiateTrade() {
  console.log("Initiate button clicked.");
  const atmStrike = findAtmStrike();
  if (!atmStrike) return;

  const strikes = [atmStrike - STRIKE_DIFFERENCE, atmStrike, atmStrike + STRIKE_DIFFERENCE];
  const ordersToPlace = strikes.flatMap(strike => [{ strike, optionType: 'CE' }, { strike, optionType: 'PE' }]);

  const confirmation = confirm(`This will SELL 3 straddles at strikes: ${strikes.join(', ')}. Proceed?`);
  if (!confirmation) return;

  for (const order of ordersToPlace) {
    await executeOrder(order, "SELL");
    await new Promise(resolve => setTimeout(resolve, 300)); // Delay between orders
  }

  initiatedStrikes = strikes.sort((a, b) => a - b);
  console.log("Initiation complete. Tracking strikes:", initiatedStrikes);
  checkPositions();
}

// Function to handle the "Roll Up" button click
async function rollUp() {
  if (initiatedStrikes.length !== 3) return alert("Not tracking three active straddles.");
  const lowestStrike = initiatedStrikes[0];
  const newHighestStrike = initiatedStrikes[2] + STRIKE_DIFFERENCE;

  if (!confirm(`This will:\n- BUY back the ${lowestStrike} straddle\n- SELL a new straddle at ${newHighestStrike}\n\nProceed?`)) return;

  await executeOrder({ strike: lowestStrike, optionType: 'CE' }, "BUY");
  await executeOrder({ strike: lowestStrike, optionType: 'PE' }, "BUY");
  await executeOrder({ strike: newHighestStrike, optionType: 'CE' }, "SELL");
  await executeOrder({ strike: newHighestStrike, optionType: 'PE' }, "SELL");

  initiatedStrikes = [initiatedStrikes[1], initiatedStrikes[2], newHighestStrike].sort((a, b) => a - b);
  alert(`Roll Up complete. Now tracking: ${initiatedStrikes.join(', ')}`);
}

// Function to handle the "Roll Down" button click
async function rollDown() {
  if (initiatedStrikes.length !== 3) return alert("Not tracking three active straddles.");
  const highestStrike = initiatedStrikes[2];
  const newLowestStrike = initiatedStrikes[0] - STRIKE_DIFFERENCE;

  if (!confirm(`This will:\n- BUY back the ${highestStrike} straddle\n- SELL a new straddle at ${newLowestStrike}\n\nProceed?`)) return;

  await executeOrder({ strike: highestStrike, optionType: 'CE' }, "BUY");
  await executeOrder({ strike: highestStrike, optionType: 'PE' }, "BUY");
  await executeOrder({ strike: newLowestStrike, optionType: 'CE' }, "SELL");
  await executeOrder({ strike: newLowestStrike, optionType: 'PE' }, "SELL");

  initiatedStrikes = [newLowestStrike, initiatedStrikes[0], initiatedStrikes[1]].sort((a, b) => a - b);
  alert(`Roll Down complete. Now tracking: ${initiatedStrikes.join(', ')}`);
}

// Function to get active positions by scraping the DOM
function getActivePositions() {
  const positionRows = document.querySelectorAll("#open-table tr.mat-row");
  const activePositions = [];
  positionRows.forEach(row => {
    const nameElement = row.querySelector("span.textoverflow");
    const quantityElement = row.querySelector("span.PositionQuantity");
    if (nameElement && quantityElement) {
      const name = nameElement.innerText.trim();
      const quantity = parseInt(quantityElement.innerText.trim().replace(/,/g, ''), 10);
      const parts = name.split(' ');
      if (parts.length >= 4) {
        const optionType = parts[parts.length - 1];
        const strikePrice = parseInt(parts[parts.length - 2], 10);
        if ((optionType === 'PUT' || optionType === 'CALL') && !isNaN(strikePrice) && !isNaN(quantity)) {
          activePositions.push({
            strike: strikePrice,
            optionType: optionType === 'CALL' ? 'CE' : 'PE',
            quantity: quantity,
          });
        }
      }
    }
  });
  return activePositions;
}

// Function to check for active positions and enable/disable buttons
function checkPositions() {
  const rollUpButton = document.getElementById("roll-up-button");
  const rollDownButton = document.getElementById("roll-down-button");

  if (initiatedStrikes.length !== 3) {
    rollUpButton.disabled = true;
    rollDownButton.disabled = true;
    return;
  }

  const positions = getActivePositions();
  const foundStraddles = initiatedStrikes.filter(strike => {
    const hasCE = positions.some(p => p.strike === strike && p.optionType === 'CE' && p.quantity < 0);
    const hasPE = positions.some(p => p.strike === strike && p.optionType === 'PE' && p.quantity < 0);
    return hasCE && hasPE;
  }).length;

  const allStraddlesActive = (foundStraddles === 3);
  rollUpButton.disabled = !allStraddlesActive;
  rollDownButton.disabled = !allStraddlesActive;
}


// --- INITIALIZATION ---

// Function to add the custom buttons to the page and attach listeners
function initialize() {
  const buttonContainer = document.createElement("div");
  buttonContainer.style.position = "fixed";
  buttonContainer.style.top = "100px";
  buttonContainer.style.right = "20px";
  buttonContainer.style.zIndex = "1000";
  buttonContainer.style.display = "flex";
  buttonContainer.style.flexDirection = "column";
  buttonContainer.style.gap = "10px";

  const initiateButton = document.createElement("button");
  initiateButton.innerText = "Initiate";
  initiateButton.id = "initiate-button";
  initiateButton.addEventListener("click", initiateTrade);

  const rollUpButton = document.createElement("button");
  rollUpButton.innerText = "Roll Up";
  rollUpButton.id = "roll-up-button";
  rollUpButton.disabled = true;
  rollUpButton.addEventListener("click", rollUp);

  const rollDownButton = document.createElement("button");
  rollDownButton.innerText = "Roll Down";
  rollDownButton.id = "roll-down-button";
  rollDownButton.disabled = true;
  rollDownButton.addEventListener("click", rollDown);

  buttonContainer.appendChild(initiateButton);
  buttonContainer.appendChild(rollUpButton);
  buttonContainer.appendChild(rollDownButton);

  document.body.appendChild(buttonContainer);
  console.log("Custom buttons added and listeners attached.");

  // Periodically check positions to update button states
  setInterval(checkPositions, 5000); // Check every 5 seconds
  checkPositions(); // Initial check
}

initialize();