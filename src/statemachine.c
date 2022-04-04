#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <ctype.h>
#include <signal.h>
#include <errno.h>

#include "common.h"
#include "statemachine.h"
#include "mcp23017.h"
#include "mcp9808.h"
#include "ads1115.h"

state_config_t state_config;

const char *token_str[] = {
	"PWR_ON",
	"OPERATE",
	"RX",
	"V_TX",
	"U_TX",
	"L_TX",

	"RX_SWAP_ON",
	"RX_SWAP_OFF",

	"V_LEFT",
	"V_RIGHT",
	"V_TX_ON",
	"V_TX_OFF",

	"U_LEFT",
	"U_RIGHT",
	"U_TX_ON",
	"U_TX_OFF",

	"L_TX_ON",
	"L_TX_OFF",

	"SHUTDOWN",
	"KILL",

	"STATUS",
	"GETTEMP",
	"V_POWER",
	"U_POWER",
	"L_POWER",
	"MAX_TOKENS"
};

const char *state_str[] = {
	"INIT",
	"SYS_PWR_ON",
	"STANDBY",

	"RX_ONLY",
	"V_TRAN",
	"U_TRAN",
	"L_TRAN",
	"MAX_STATES"
};

const char *secstate_str[] = {
	"NONE",

	"RECEIVE",
	"RX_SWITCH",
	"RX_SHUTDOWN",
	"RX_RX_SWAP_ON",
	"RX_RX_SWAP_OFF",
	"RX_VHF_LHCP",
	"RX_VHF_RHCP",
	"RX_UHF_LHCP",
	"RX_UHF_RHCP",

	"VHF_TRANSMIT",
	"V_SWITCH",
	"V_SHUTDOWN",
	"V_PA_COOL",
	"V_PA_DOWN",
	"V_RX_SWAP_ON",
	"V_RX_SWAP_OFF",
	"V_UHF_LHCP",
	"V_UHF_RHCP",
	"V_TRANS_ON",
	"V_TRANS_OFF",
	"V_LHCP",
	"V_RHCP",

	"UHF_TRANSMIT",
	"U_SWITCH",
	"U_SHUTDOWN",
	"U_PA_COOL",
	"U_PA_DOWN",
	"U_RX_SWAP_ON",
	"U_RX_SWAP_OFF",
	"U_VHF_LHCP",
	"U_VHF_RHCP",
	"U_TRANS_ON",
	"U_TRANS_OFF",
	"U_LHCP",
	"U_RHCP",

	"L_TRANSMIT",
	"L_SWITCH",
	"L_SHUTDOWN",
	"L_PA_COOL",
	"L_PA_DOWN",
	"L_RX_SWAP_ON",
	"L_RX_SWAP_OFF",
	"L_VHF_LHCP",
	"L_VHF_RHCP",
	"L_TRANS_ON",
	"L_TRANS_OFF",
	"L_UHF_LHCP",
	"L_UHF_RHCP",
	"MAX_SEC_STATES"
};

void init_statemachine(void)
{
	/* Set initial state machine states */
	state_config.state = INIT;
	state_config.sec_state = NONE;

	/* Open the I2C device for read/write */
	if ((i2c_fd = open(i2c_dev, O_RDWR)) < 0) {
		logmsg(LOG_ERR,"Error: Failed to open i2c device \'%s\': %s\n", i2c_dev, strerror(errno));
		exit(EXIT_FAILURE);
	}

	/* Initialize I2C devices */
	MCP23017Init(i2c_fd);
}

void handle_alarm_signal(int sig)
{
	if (state_config.state == SYS_PWR_ON) {
		state_config.next_state = STANDBY;
		changeState();
	} else if (state_config.state == V_TRAN && state_config.sec_state == V_PA_COOL) {
		state_config.sec_state = V_PA_DOWN;
		MCP23017BitClear(i2c_fd, V_PA_BIT);
		MCP23017BitClear(i2c_fd, V_KEY_BIT);
		state_config.state = STANDBY;
		state_config.sec_state = NONE;
	} else if (state_config.state == U_TRAN && state_config.sec_state == U_PA_COOL) {
		state_config.sec_state = U_PA_DOWN;
		MCP23017BitClear(i2c_fd, U_PA_BIT);
		MCP23017BitClear(i2c_fd, U_KEY_BIT);
		state_config.state = STANDBY;
		state_config.sec_state = NONE;
	} else if (state_config.state == L_TRAN && state_config.sec_state == L_PA_COOL) {
		state_config.sec_state = L_PA_DOWN;
		MCP23017BitClear(i2c_fd, L_PA_BIT);
		state_config.state = STANDBY;
		state_config.sec_state = NONE;
	} else {
		stateWarning();
	}
}

void i2c_exit(void)
{
	logmsg(LOG_NOTICE, "Shutting down I2C...\n");
	MCP23017BitReset(i2c_fd);

	if (close(i2c_fd) < 0) {
		logmsg(LOG_ERR,"Error: Failed to close I2C device: %s\n", strerror(errno));
	}
	logmsg(LOG_DEBUG, "I2C shut down\n");
}

token_t parse_token(const char *token)
{
	token_t i;
	for (i = 0; i < MAX_TOKENS; i++) {
		if (!strcmp(token, token_str[i])) {
			logmsg(LOG_DEBUG, "Token entered: %s\n", token_str[i]);
			break;
		}
	}
	return i;
}

void processToken(void)
{
	if (state_config.token == KILL) {
		state_config.next_state = INIT;
		state_config.next_sec_state =  NONE;
		return;
	}
	switch(state_config.state) {
	case INIT:
		if(state_config.token == PWR_ON)
			state_config.next_state = SYS_PWR_ON;
		else
			tokenError();
		break;
	case SYS_PWR_ON:
		if(state_config.token == OPERATE)
			state_config.next_state = STANDBY;
		else
			tokenError();
		break;
	case STANDBY:
		if(state_config.token == RX) {
			state_config.next_state = RX_ONLY;
			state_config.next_sec_state = RECEIVE;
		}
		else if(state_config.token == V_TX) {
			state_config.next_state = V_TRAN;
			state_config.next_sec_state = VHF_TRANSMIT;
		}
		else if(state_config.token == U_TX) {
			state_config.next_state = U_TRAN;
			state_config.next_sec_state = UHF_TRANSMIT;
		}
		else if(state_config.token == L_TX) {
			state_config.next_state = L_TRAN;
			state_config.next_sec_state = L_TRANSMIT;
		}
		else
			tokenError();
		break;

	case RX_ONLY:
		processRXTokens();
		break;

	case V_TRAN:
		processVHFTokens();
		break;

	case U_TRAN:
		processUHFTokens();
		break;

	case L_TRAN:
		processLBandTokens();
		break;

	default:
		tokenError();
		break;
	}
}


void processRXTokens(void)
{
	switch(state_config.sec_state) {
	case RECEIVE:
	case RX_SWITCH:
		if (state_config.token == RX_SWAP_ON)
			state_config.next_sec_state =  RX_RX_SWAP_ON;
		else if (state_config.token == RX_SWAP_OFF)
			state_config.next_sec_state =  RX_RX_SWAP_OFF;
		else if(state_config.token == V_LEFT)
			state_config.next_sec_state =  RX_VHF_LHCP;
		else if(state_config.token == V_RIGHT)
			state_config.next_sec_state =  RX_VHF_RHCP;
		else if(state_config.token == U_LEFT)
			state_config.next_sec_state =  RX_UHF_LHCP;
		else if(state_config.token == U_RIGHT)
			state_config.next_sec_state =  RX_UHF_RHCP;
		else if(state_config.token == SHUTDOWN)
			state_config.next_sec_state =  RX_SHUTDOWN;
		else
			tokenError();
		break;
	case RX_RX_SWAP_ON:
	case RX_RX_SWAP_OFF:
	case RX_VHF_LHCP:
	case RX_VHF_RHCP:
	case RX_UHF_LHCP:
	case RX_UHF_RHCP:
		ErrorRecovery(RX_SWITCH);
		break;
	case RX_SHUTDOWN:
		break;
	default:
		tokenError();
		break;
	}
}


void processVHFTokens(void)
{
	switch(state_config.sec_state) {
	case VHF_TRANSMIT:
	case V_SWITCH:
		if (state_config.token == RX_SWAP_ON)
			state_config.next_sec_state =  V_RX_SWAP_ON;
		else if (state_config.token == RX_SWAP_OFF)
			state_config.next_sec_state =  V_RX_SWAP_OFF;
		else if(state_config.token == V_LEFT)
			state_config.next_sec_state =  V_LHCP;
		else if(state_config.token == V_RIGHT)
			state_config.next_sec_state =  V_RHCP;
		else if(state_config.token == V_TX_ON)
			state_config.next_sec_state =  V_TRANS_ON;
		else if(state_config.token == V_TX_OFF)
			state_config.next_sec_state =  V_TRANS_OFF;
		else if(state_config.token == U_RIGHT)
			state_config.next_sec_state =  V_UHF_RHCP;
		else if(state_config.token == U_LEFT)
			state_config.next_sec_state =  V_UHF_LHCP;
		else if(state_config.token == SHUTDOWN)
			state_config.next_sec_state =  V_SHUTDOWN;
		else
			tokenError();
		break;
	case V_RX_SWAP_ON:
	case V_RX_SWAP_OFF:
	case V_LHCP:
	case V_RHCP:
	case V_UHF_RHCP:
	case V_UHF_LHCP:
	case V_PA_DOWN:
	case V_TRANS_ON:
	case V_TRANS_OFF:
		ErrorRecovery(V_SWITCH);
		break;
	case V_SHUTDOWN:
	case V_PA_COOL:
		CoolDown_Wait();
		break;
	default:
		tokenError();
		break;
	}
}


void processUHFTokens(void)
{
	switch(state_config.sec_state) {
	case UHF_TRANSMIT:
	case U_SWITCH:
		if (state_config.token == RX_SWAP_ON)
			state_config.next_sec_state =  U_RX_SWAP_ON;
		if (state_config.token == RX_SWAP_OFF)
			state_config.next_sec_state =  U_RX_SWAP_OFF;
		else if(state_config.token == U_LEFT)
			state_config.next_sec_state =  U_LHCP;
		else if(state_config.token == U_RIGHT)
			state_config.next_sec_state =  U_RHCP;
		else if(state_config.token == U_TX_ON)
			state_config.next_sec_state =  U_TRANS_ON;
		else if(state_config.token == U_TX_OFF)
			state_config.next_sec_state =  U_TRANS_OFF;
		else if(state_config.token == V_RIGHT)
			state_config.next_sec_state =  U_VHF_RHCP;
		else if(state_config.token == V_LEFT)
			state_config.next_sec_state =  U_VHF_LHCP;
		else if(state_config.token == SHUTDOWN)
			state_config.next_sec_state =  U_SHUTDOWN;
		else
			tokenError();
		break;
	case U_RX_SWAP_ON:
	case U_RX_SWAP_OFF:
	case U_LHCP:
	case U_RHCP:
	case U_VHF_RHCP:
	case U_VHF_LHCP:
	case U_PA_DOWN:
	case U_TRANS_ON:
	case U_TRANS_OFF:
		ErrorRecovery(U_SWITCH);
		break;
	case U_SHUTDOWN:
	case U_PA_COOL:
		CoolDown_Wait();
		break;
	default:
		tokenError();
		break;
	}
}


void processLBandTokens(void)
{
	switch(state_config.sec_state) {
	case L_TRANSMIT:
	case L_SWITCH:
		if (state_config.token == RX_SWAP_ON)
			state_config.next_sec_state =  L_RX_SWAP_ON;
		if (state_config.token == RX_SWAP_OFF)
			state_config.next_sec_state =  L_RX_SWAP_OFF;
		else if(state_config.token == U_LEFT)
			state_config.next_sec_state =  L_UHF_LHCP;
		else if(state_config.token == U_RIGHT)
			state_config.next_sec_state =  L_UHF_RHCP;
		else if(state_config.token == L_TX_ON)
			state_config.next_sec_state =  L_TRANS_ON;
		else if(state_config.token == L_TX_OFF)
			state_config.next_sec_state =  L_TRANS_OFF;
		else if(state_config.token == V_RIGHT)
			state_config.next_sec_state =  L_VHF_RHCP;
		else if(state_config.token == V_LEFT)
			state_config.next_sec_state =  L_VHF_LHCP;
		else if(state_config.token == SHUTDOWN)
			state_config.next_sec_state =  L_SHUTDOWN;
		else
			tokenError();
		break;
	case L_RX_SWAP_ON:
	case L_RX_SWAP_OFF:
	case L_VHF_LHCP:
	case L_VHF_RHCP:
	case L_UHF_RHCP:
	case L_UHF_LHCP:
	case L_PA_DOWN:
	case L_TRANS_ON:
	case L_TRANS_OFF:
		ErrorRecovery(L_SWITCH);
		break;
	case L_SHUTDOWN:
	case L_PA_COOL:
		CoolDown_Wait();
		break;
	default:
		tokenError();
		break;
	}
}



void ErrorRecovery(state_t recovery_state)
{
	logmsg(LOG_WARNING, "The system should not have been in this state. Corrective action taken.\n");
	logmsg(LOG_WARNING, "Please reenter your token and manually validate the action.\n");
	state_config.next_state = recovery_state;
}

void tokenError(void)
{
	logmsg (LOG_WARNING, "Token not valid for the state. Please refer to state diagram. No action taken.\n");
}

void stateError(void)
{
	logmsg(LOG_ERR, "ERROR: There is a program error. Contact coder.\n");
	logmsg(LOG_ERR, "Results unpredictable. Please Kill and start over.\n");
}

void stateWarning(void)
{
	logmsg(LOG_WARNING, "The system should not have been in this state. KILL token likely entered before.\n");
}


void CoolDown_Wait(void)
{
	logmsg(LOG_WARNING, "Waiting for cooldown. No action taken. If required, force exit via KILL or EXIT tokens.\n");
}


void changeState(void)
{
	uint8_t state_save;

	logmsg(LOG_DEBUG, "Entering %s:%s State\n", state_str[state_config.next_state], secstate_str[state_config.next_sec_state]);
	switch(state_config.next_state) {
	case INIT:
		MCP23017BitReset(i2c_fd);
		state_config.state = INIT;
		state_config.sec_state = NONE;
		break;
	case SYS_PWR_ON:
		MCP23017BitSetMask(i2c_fd, SDR_ROCK|SDR_LIME|ROT_PWR);
		state_config.state = SYS_PWR_ON;
		alarm(60);
		break;
	case STANDBY:
		state_config.state = STANDBY;
		break;

	case RX_ONLY:
		state_config.state = RX_ONLY;
		switch(state_config.next_sec_state) {
		case RECEIVE:
			MCP23017BitSetMask(i2c_fd, U_LNA|V_LNA);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_SWITCH:
			break;
		case RX_SHUTDOWN:
			MCP23017BitClearMask(i2c_fd, U_POL|V_POL|V_LNA|U_LNA|RX_SWAP);
			state_config.state = STANDBY;
			state_config.sec_state = NONE;
			break;
		case RX_RX_SWAP_ON:
			MCP23017BitSetMask(i2c_fd, RX_SWAP);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_RX_SWAP_OFF:
			MCP23017BitClearMask(i2c_fd, RX_SWAP);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_VHF_LHCP:
			MCP23017BitSetMask(i2c_fd, V_POL);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_VHF_RHCP:
			MCP23017BitClearMask(i2c_fd, V_POL);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_UHF_LHCP:
			MCP23017BitSetMask(i2c_fd, U_POL);
			state_config.sec_state = RX_SWITCH;
			break;
		case RX_UHF_RHCP:
			MCP23017BitClearMask(i2c_fd, U_POL);
			state_config.sec_state = RX_SWITCH;
			break;
		default:
			stateError();
			break;
		}
		break;

	case V_TRAN:
		state_config.state = V_TRAN;
		switch(state_config.next_sec_state) {
		case VHF_TRANSMIT:
			MCP23017BitSetMask(i2c_fd, U_LNA|V_PA|V_KEY);
			state_config.sec_state = V_SWITCH;
			break;
		case V_SWITCH:
			break;
		case V_SHUTDOWN:
			MCP23017BitClearMask(i2c_fd, U_LNA|U_POL|V_POL|V_PTT|RX_SWAP);
			state_config.sec_state = V_PA_COOL;
			alarm(120);
			break;
		case V_PA_COOL:
		case V_PA_DOWN:
			break;
		case V_RX_SWAP_ON:
			MCP23017BitSetMask(i2c_fd, RX_SWAP);
			state_config.sec_state = V_SWITCH;
			break;
		case V_RX_SWAP_OFF:
			MCP23017BitClearMask(i2c_fd, RX_SWAP);
			state_config.sec_state = V_SWITCH;
			break;
		case V_UHF_LHCP:
			MCP23017BitSetMask(i2c_fd, U_POL);
			state_config.sec_state = V_SWITCH;
			break;
		case V_UHF_RHCP:
			MCP23017BitClearMask(i2c_fd, U_POL);
			state_config.sec_state = V_SWITCH;
			break;
		case V_TRANS_ON:
			MCP23017BitSetMask(i2c_fd, V_PTT);
			state_config.sec_state = V_SWITCH;
			break;
		case V_TRANS_OFF:
			MCP23017BitClearMask(i2c_fd, V_PTT);
			state_config.sec_state = V_SWITCH;
			break;
		case V_LHCP:
			state_save = MCP23017BitRead(i2c_fd, V_PTT_BIT);
			MCP23017BitClear(i2c_fd, V_PTT_BIT);
			usleep(100);
			MCP23017BitSet(i2c_fd, V_POL_BIT);
			usleep(100);
			if(state_save)
				MCP23017BitSet(i2c_fd, V_PTT_BIT);
			else
				MCP23017BitClear(i2c_fd, V_PTT_BIT);
			state_config.sec_state = V_SWITCH;
			break;

		case V_RHCP:
			state_save = MCP23017BitRead(i2c_fd, V_PTT_BIT);
			MCP23017BitClear(i2c_fd, V_PTT_BIT);
			usleep(100);
			MCP23017BitClear(i2c_fd, V_POL_BIT);
			usleep(100);
			if(state_save)
				MCP23017BitSet(i2c_fd, V_PTT_BIT);
			else
				MCP23017BitClear(i2c_fd, V_PTT_BIT);
			state_config.sec_state = V_SWITCH;
			break;
		default:
			stateError();
			break;
		}
		break;

	case U_TRAN:
		state_config.state = U_TRAN;
		switch(state_config.next_sec_state) {
		case UHF_TRANSMIT:
			MCP23017BitSetMask(i2c_fd, V_LNA|U_PA|U_KEY);
			state_config.sec_state = U_SWITCH;
			break;
		case U_SWITCH:
			break;
		case U_SHUTDOWN:
			MCP23017BitClearMask(i2c_fd, V_LNA|V_POL|U_POL|U_PTT|RX_SWAP);
			state_config.sec_state = U_PA_COOL;
			alarm(120);
			break;
		case U_PA_COOL:
		case U_PA_DOWN:
			break;
		case U_RX_SWAP_ON:
			MCP23017BitSetMask(i2c_fd, RX_SWAP);
			state_config.sec_state = U_SWITCH;
			break;
		case U_RX_SWAP_OFF:
			MCP23017BitClearMask(i2c_fd, RX_SWAP);
			state_config.sec_state = U_SWITCH;
			break;
		case U_VHF_LHCP:
			MCP23017BitSetMask(i2c_fd, V_POL);
			state_config.sec_state = U_SWITCH;
			break;
		case U_VHF_RHCP:
			MCP23017BitClearMask(i2c_fd, V_POL);
			state_config.sec_state = U_SWITCH;
			break;
		case U_TRANS_ON:
			MCP23017BitSetMask(i2c_fd, U_PTT);
			state_config.sec_state = U_SWITCH;
			break;
		case U_TRANS_OFF:
			MCP23017BitClearMask(i2c_fd, U_PTT);
			state_config.sec_state = U_SWITCH;
			break;
		case U_LHCP:
			state_save = MCP23017BitRead(i2c_fd, U_PTT_BIT);
			MCP23017BitClear(i2c_fd, U_PTT_BIT);
			usleep(100);
			MCP23017BitSet(i2c_fd, U_POL_BIT);
			usleep(100);
			if(state_save)
				MCP23017BitSet(i2c_fd, U_PTT_BIT);
			else
				MCP23017BitClear(i2c_fd, U_PTT_BIT);
			state_config.sec_state = U_SWITCH;
			break;

		case U_RHCP:
			state_save = MCP23017BitRead(i2c_fd, U_PTT_BIT);
			MCP23017BitClear(i2c_fd, U_PTT_BIT);
			usleep(100);
			MCP23017BitClear(i2c_fd, U_POL_BIT);
			usleep(100);
			if(state_save)
				MCP23017BitSet(i2c_fd, U_PTT_BIT);
			else
				MCP23017BitClear(i2c_fd, U_PTT_BIT);
			state_config.sec_state = U_SWITCH;
			break;
		default:
			stateError();
			break;
		}
		break;

	case L_TRAN:
		state_config.state = L_TRAN;
		switch(state_config.next_sec_state) {
		case L_TRANSMIT:
			MCP23017BitSetMask(i2c_fd, U_LNA|V_LNA|L_PA);
			state_config.sec_state = L_SWITCH;
			break;
		case L_SWITCH:
			break;
		case L_SHUTDOWN:
			MCP23017BitClearMask(i2c_fd, L_PTT|U_POL|V_POL|V_LNA|U_LNA|RX_SWAP);
			state_config.sec_state = L_PA_COOL;
			alarm(120);
			break;
		case L_PA_COOL:
		case L_PA_DOWN:
			break;
		case L_RX_SWAP_ON:
			MCP23017BitSetMask(i2c_fd, RX_SWAP);
			state_config.sec_state = L_SWITCH;
			break;
		case L_RX_SWAP_OFF:
			MCP23017BitClearMask(i2c_fd, RX_SWAP);
			state_config.sec_state = L_SWITCH;
			break;
		case L_UHF_LHCP:
			MCP23017BitSetMask(i2c_fd, U_POL);
			state_config.sec_state = L_SWITCH;
			break;
		case L_UHF_RHCP:
			MCP23017BitClearMask(i2c_fd, U_POL);
			state_config.sec_state = L_SWITCH;
			break;
		case L_TRANS_ON:
			MCP23017BitSetMask(i2c_fd, L_PTT);
			state_config.sec_state = L_SWITCH;
			break;
		case L_TRANS_OFF:
			MCP23017BitClearMask(i2c_fd, L_PTT);
			state_config.sec_state = L_SWITCH;
			break;
		case L_VHF_LHCP:
			MCP23017BitSetMask(i2c_fd, V_POL);
			state_config.sec_state = L_SWITCH;
			break;
		case L_VHF_RHCP:
			MCP23017BitClearMask(i2c_fd, V_POL);
			state_config.sec_state = L_SWITCH;
			break;
		default:
			stateError();
			break;
		}
		break;

	default:
		stateError();
		break;
	}
}
