#ifndef _STATEMACHINE_H_
#define _STATEMACHINE_H_

#include <stdint.h>
#include "mcp23017.h"
#include "mcp9808.h"
#include "ads1115.h"

#define BIT_MASK(n)     (0x1 << n)

#define ROT_PWR_BIT     0
#define SDR_ROCK_BIT    1
#define V_PA_BIT        2
#define SDR_LIME_BIT    3
#define L_PA_BIT        4
#define U_PA_BIT        5
#define U_PTT_BIT       6
#define RX_SWAP_BIT      7
#define L_PTT_BIT       8
#define V_PTT_BIT       9
#define V_POL_BIT       10
#define U_POL_BIT       11
#define U_KEY_BIT       12
#define V_KEY_BIT       13
#define V_LNA_BIT       14
#define U_LNA_BIT       15

#define ROT_PWR         BIT_MASK(ROT_PWR_BIT)
#define SDR_ROCK        BIT_MASK(SDR_ROCK_BIT)
#define V_PA            BIT_MASK(V_PA_BIT)
#define SDR_LIME        BIT_MASK(SDR_LIME_BIT)
#define L_PA            BIT_MASK(L_PA_BIT)
#define U_PA            BIT_MASK(U_PA_BIT)
#define U_PTT           BIT_MASK(U_PTT_BIT)
#define RX_SWAP         BIT_MASK(RX_SWAP_BIT)
#define L_PTT           BIT_MASK(L_PTT_BIT)
#define V_PTT           BIT_MASK(V_PTT_BIT)
#define V_POL           BIT_MASK(V_POL_BIT)
#define U_POL           BIT_MASK(U_POL_BIT)
#define U_KEY           BIT_MASK(U_KEY_BIT)
#define V_KEY           BIT_MASK(V_KEY_BIT)
#define V_LNA           BIT_MASK(V_LNA_BIT)
#define U_LNA           BIT_MASK(U_LNA_BIT)

extern const char *token_str[];
extern const char *state_str[];
extern const char *secstate_str[];
extern char *i2c_dev;
extern int i2c_fd;

typedef enum {
	PWR_ON,
	OPERATE,
	RX,
	V_TX,
	U_TX,
	L_TX,

	RX_SWAP_ON,
	RX_SWAP_OFF,

	V_LEFT,
	V_RIGHT,
	V_TX_ON,
	V_TX_OFF,

	U_LEFT,
	U_RIGHT,
	U_TX_ON,
	U_TX_OFF,

	L_TX_ON,
	L_TX_OFF,

	SHUTDOWN,
	KILL,

	STATUS,
	GETTEMP,
	V_POWER,
	U_POWER,
	L_POWER,
	MAX_TOKENS
} token_t;

typedef enum {
	INIT,
	SYS_PWR_ON,
	STANDBY,

	RX_ONLY,
	V_TRAN,
	U_TRAN,
	L_TRAN,
	MAX_STATES
} state_t;

typedef enum {
	NONE,

	RECEIVE,
	RX_SWITCH,
	RX_SHUTDOWN,
	RX_RX_SWAP_ON,
	RX_RX_SWAP_OFF,
	RX_VHF_LHCP,
	RX_VHF_RHCP,
	RX_UHF_LHCP,
	RX_UHF_RHCP,

	VHF_TRANSMIT,
	V_SWITCH,
	V_SHUTDOWN,
	V_PA_COOL,
	V_PA_DOWN,
	V_RX_SWAP_ON,
	V_RX_SWAP_OFF,
	V_UHF_LHCP,
	V_UHF_RHCP,
	V_TRANS_ON,
	V_TRANS_OFF,
	V_LHCP,
	V_RHCP,

	UHF_TRANSMIT,
	U_SWITCH,
	U_SHUTDOWN,
	U_PA_COOL,
	U_PA_DOWN,
	U_RX_SWAP_ON,
	U_RX_SWAP_OFF,
	U_VHF_LHCP,
	U_VHF_RHCP,
	U_TRANS_ON,
	U_TRANS_OFF,
	U_LHCP,
	U_RHCP,

	L_TRANSMIT,
	L_SWITCH,
	L_SHUTDOWN,
	L_PA_COOL,
	L_PA_DOWN,
	L_RX_SWAP_ON,
	L_RX_SWAP_OFF,
	L_VHF_LHCP,
	L_VHF_RHCP,
	L_TRANS_ON,
	L_TRANS_OFF,
	L_UHF_LHCP,
	L_UHF_RHCP,
	MAX_SEC_STATES
} sec_state_t;


typedef struct _state_config {
	state_t state;
	state_t next_state;
	sec_state_t sec_state;
	sec_state_t next_sec_state;
	token_t token;
	int errorCode;
} state_config_t;

extern state_config_t state_config;

void handle_alarm_signal(int sig);
void init_statemachine(void);
void i2c_exit(void);
token_t parse_token(const char *token);
void processToken(void);
void processRXTokens(void);
void processVHFTokens(void);
void processUHFTokens(void);
void processLBandTokens(void);
void ErrorRecovery(state_t recovery_state);
void CoolDown_Wait(void);
void tokenError(void);
void stateError(void);
void stateWarning(void);
void changeState(void);

#endif
