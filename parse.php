<?php

# global var that counts how many lines of stdin were processed
# only for error messages and logging
$line = 0;

function parse_argv($argv){
  /*
  Parses argv for parameters
  IN: argv - array of strings
  OUT: dictionary
    fail - 0 if all is fine
      10 if calling help with another param
    help - 1 if help param called, 0 otherwise
  */
  $ctrl = array(
    "help"=>0
  );
  // only valid options are no args or the help arg on its own
  if ( (in_array("--help", $argv) || in_array("-h", $argv)) && sizeof($argv) == 2){
    $ctrl["help"] = 1;
  } elseif (sizeof($argv) != 1){
    echo "Err10: Invalid or too many arguments";
    exit(10);
  }
  return $ctrl;
}

function print_help($scrname){
  /*
  Prints help string
  IN: scrname - string, name of this file
  */
  $haelp = "\nThis is an IPPcode22 parser\n";
  $haelp .= "Input is read from stdin\n";
  $haelp .= "The output is indented xml representation of the code, which is written to stdout\n";
  $haelp .= "Script calling format:\n";
  #$haelp .= "php ".$scrname." [params]\n";
  #$haelp .= "or\n";
  $haelp .= "php8.1 ".$scrname." [params]\n";
  $haelp .= "Params must be separated by at least one whitespace character\n";
  $haelp .= "\nAvailable params:\n";
  $haelp .= "--help\tPrints this\n";
  $haelp .= "\n";
  echo $haelp;
  return;
}

function xml_string_conv($str){
  /*
  xml string friendlifier
  Replaces xml control characters with xml representations
  Replaces ampersand (&), gt (>), lt (<), apostrophe ('), and quote(")
  IN: str - string
  OUT: string
  */
  $str = preg_replace("/&/", "&amp", $str);
  $str = preg_replace("/</", "&lt", $str);
  $str = preg_replace("/>/", "&gt", $str);
  $str = preg_replace('/\"/', "&quot", $str);
  $str = preg_replace("/\'/", "&apos", $str);
  return $str;
}

function xml_var($varstr, $argord){
  /*
  Builds a var type arg
  Forces frame identifier to caps
  Calls xml_string_conv on var identifier
  IN: varstr - string, assembly variable,
      eg 'LF@pootis'
    argord - int, order of arg in instruction
  OUT: string, xml arg block
  */
  check_valid_id($varstr);
  return "  <arg".$argord." type=\"var\">".strtoupper(substr($varstr, 0, 2)).substr(xml_string_conv($varstr), 2)."</arg".$argord.">\n";
}

function xml_label($varstr, $argord){
  /*
  Builds the inside of a label type arg
  Calls xml_string_conv on label identifier
  IN: varstr - string, assembly label name
    argord - int, order of arg in instruction
  OUT: string, xml arg block
  */
  check_valid_id($varstr);
  return "  <arg".$argord." type=\"label\">".xml_string_conv($varstr)."</arg".$argord.">\n";
}

function xml_sym($varstr, $argord){
  /*
  Builds the inside of a symbol type arg
  If var, calls xml_var
  Otherwise separates type and value
  If string, calls xml_string_conv on value
  IN: varstr - string, assembly symbol,
      eg 'string@stout\032shako\032for\0322\032refined'
    argord - int, order of arg in instruction
  OUT: string, xml arg block
  */
  GLOBAL $line;
  #echo "xml_sym $varstr\n";
  switch(strtoupper(preg_split('/@/', $varstr)[0])){
    case "BOOL":
      switch(strtolower(substr($varstr, 5))){
        case "true":
        case "false":
          return "  <arg".$argord." type=\"bool\">".strtolower(substr($varstr, 5))."</arg".$argord.">\n";
        default:
          # invalid arg value
          echo "Err23: Invalid bool value on line $line: $varstr";
          exit(23);
        }
    case "INT":
      if (check_valid_int($varstr)){
        return "  <arg".$argord." type=\"int\">".substr($varstr, 4)."</arg".$argord.">\n";
      } else {
        # invalid arg value
        echo "Err23: Invalid int format on line $line: $varstr";
        exit(23);
      }
    case "NIL":
      if (strtolower(substr($varstr, 4)) == "nil"){
        return "  <arg".$argord." type=\"nil\">nil</arg".$argord.">\n";
      } else {
        # invalid arg value
        echo "Err23: Invalid nil value on line $line: $varstr";
        exit(23);
      }
    case "STRING":
      if (check_valid_string($varstr)){
        return "  <arg".$argord." type=\"string\">".xml_string_conv(substr($varstr, 7))."</arg".$argord.">\n";
      } else {
        # invalid arg value
        echo "Err23: Invalid escape sequence on line $line: $varstr";
        exit(23);
      }
    case "GF":
    case "LF":
    case "TF":
      return xml_var($varstr, $argord);
    default:
      # invalid var type
      echo "Err23: Invalid variable type on line $line: $varstr";
      exit(23);
  }
}

function xml_type($varstr, $argord){
  /*
  Builds the inside of a type type arg
  Separates type and value
  IN: varstr - string, assembly type,
      eg 'type@bool'
    argord - int, order of arg in instruction
  OUT: string, xml arg block
  */
  GLOBAL $line;
  switch(strtolower(substr($varstr, 0, 6))){
    case "bool":
    case "int":
    case "string":
      return "  <arg".$argord." type=\"type\">".substr($varstr, 0, 6)."</arg".$argord.">\n";
    default:
      # invalid arg value
      echo "Err23: Invalid type value on line $line: $varstr";
      exit(23);
  }
}

function is_it_($varstr, $type){
  /*
  Checks if a given assembly symbol is a given type
  IN: varstr - string, symbol
    type - string, type
  OUT: bool, true if the type matches, false otherwise
  */
  switch($type){
    case "bool":
      return(strtoupper(substr($varstr, 0, 2)) == "BO");
    case "int":
      return(strtoupper(substr($varstr, 0, 2)) == "IN");
    case "nil":
      return(strtoupper(substr($varstr, 0, 2)) == "NI");
    case "string":
      return(strtoupper(substr($varstr, 0, 2)) == "ST");
    case "var":
      return(strtoupper(substr($varstr, 0, 2)) == "GF" ||
        strtoupper(substr($varstr, 0, 2)) == "LF" ||
        strtoupper(substr($varstr, 0, 2)) == "TF");
    case "type":
      return(strtoupper($varstr) == "INT" || strtoupper($varstr) == "STRING" || strtoupper($varstr) == "BOOL");
    default:
      return(false);
  }
}

function is_it_same($varstr1, $varstr2){
  /*
  Checks if 2 assembly symbols are the same type
  IN: varstr1, varstr2 - string, symbol
  OUT: bool, true if the type matches, false otherwise
  */
  $varframes = array("GF", "LF", "TF");
  return(strtoupper(substr($varstr1, 0, 2)) == strtoupper(substr($varstr2, 0, 2)) ||
    (in_array($varstr1, $varframes) && in_array($varstr2, $varframes)));
}

function check_valid_string($varstr){
  /*
  Checks if a string literal is valid
  Only checks for escseq validity
  Whitespaces and # get yeeted before this function is called
  IN: varstr - string, string literal with type, eg string@pootis
  OUT: bool, true if string is valid
    terminates script if not
  */
  $str = substr($varstr, 7);
  for ($i = 0; $i < strlen($str); $i++){
    if (ord($str[$i]) == 92){
      if (!ctype_digit(substr($str, $i + 1, 3))){
        # invalid escape sequence
        return false;
      }
    }
  }
  return true;
}

function check_valid_id($varstr){
  /*
  Checks if all characters in a var or label name are valid
  IN: varstr - string, variable or label name
  OUT: bool, true if valid
    terminates script if not
  */
  GLOBAL $line;
  $special = "_-$&%*!?";
  $stra = preg_split("/[@]/", $varstr);
  $str = $stra[count($stra) - 1];
  #print_r($stra);
  #echo $str[0], strpos($special, $str[0]) == NULL, "\n";
  if (!ctype_alpha($str[0]) && strpos($special, $str[0]) != NULL){
    # illegal identifier
    echo "Err23: Invalid identifier on line $line: $varstr";
    exit(23);
  }
  for($i = 1; $i < strlen($str); $i++){
    if (!ctype_alnum($str[$i]) && strpos($special, $str[$i]) != NULL){
      # illegal identifier
      echo "Err23: Invalid identifier on line $line: $varstr";
      exit(23);
    }
  }
  # frame check
  if (sizeof($stra) == 2){
    if (!(strtoupper($stra[0]) == "GF" || strtoupper($stra[0]) == "LF" || strtoupper($stra[0]) == "TF")){
      # illegal identifier
      echo "Err23: Invalid identifier on line $line: $varstr";
      exit(23);
    }
  }
  return true;
}

function check_valid_int($varstr){
  /*
  Checks variable is properly formatted number
  IN: varstr - string, variable or label name
  OUT: bool, true if valid
    terminates script if not
  Valid formats:
    [+,-]"0"(1-7){0-7}
    [+,-]"0b"{0,1}+
    [+,-]"0x"{0-f}+
    [+,-](1-9){0-9}[e[+,-](1-9){0-9}]
  */
  $oct_digits = "01234567";
  $dec_digits = "0123456789";
  $hex_digits = "0123456789abcdefABCDEF";
  $fsm_state = "start";
  $terminal_states = array("bin", "bin_zero", "dec", "exp", "exp_zero", "hex", "hex_zero", "oct", "zero");
  for ($i = 4; $i < strlen($varstr); $i++){
    #echo "$varstr[$i]\n";
    #echo $fsm_state, "\n";
    switch($fsm_state){
      case "bin":
        if (!($varstr[$i] == "0" || $varstr[$i] == "1")){
          $fsm_state = "fail";
        }
        break;
      case "bin_empty":
        if ($varstr[$i] == "0"){
          $fsm_state = "bin_zero";
        } elseif ($varstr[$i] == "1"){
          $fsm_state = "bin";
        } else {
          $fsm_state = "fail";
        }
        break;
      case "bin_zero":
        $fsm_state = "fail";
        break;
      case "dec":
        if ($varstr[$i] == "e" || $varstr[$i] == "E"){
          $fsm_state = "exp_empty";
        } elseif (strpos($dec_digits, $varstr[$i]) === NULL){
          $fsm_state = "fail";
        }
        break;
      case "exp":
        if (strpos($dec_digits, $varstr[$i]) == NULL){
          $fsm_state = "fail";
        }
        break;
      case "exp_empty":
        if ($varstr[$i] == "0"){
          $fsm_state = "exp_zero";
        } elseif ($varstr[$i] == "+" || $varstr[$i] == "-"){
          $fsm_state = "exp_sign";
        } elseif (strpos($dec_digits, $varstr[$i]) > 0){
          $fsm_state = "exp";
        } else {
          $fsm_state = "fail";
        }
        break;
      case "exp_sign":
        if (strpos($dec_digits, $varstr[$i]) > 0){
          $fsm_state = "exp";
        } else {
          $fsm_state = "fail";
        }
        break;
      case "exp_zero":
        $fsm_state = "fail";
        break;
      case "fail":
        break;
      case "hex":
        if (strpos($hex_digits, $varstr[$i]) == NULL){
          $fsm_state = "fail";
        }
        break;
      case "hex_empty":
        if ($varstr[$i] == "0"){
          $fsm_state = "hex_zero";
        } elseif (strpos($hex_digits, $varstr[$i]) > 0){
          $fsm_state = "hex";
        }
        break;
      case "hex_zero":
        $fsm_state = "fail";
        break;
      case "oct":
        if (strpos($oct_digits, $varstr[$i]) == NULL){
          $fsm_state = "fail";
        }
        break;
      case "start":
        if ($varstr[$i] == "0"){
          $fsm_state = "zero";
        } elseif ($varstr[$i] == "+" || $varstr[$i] == "-"){
          $fsm_state = "start_sign";
        } elseif (strpos($dec_digits, $varstr[$i]) > 0){
          $fsm_state = "dec";
        } else {
          $fsm_state = "fail";
        }
        break;
      case "start_sign":
        if ($varstr[$i] == "0"){
          $fsm_state = "zero_sign";
        }elseif (strpos($dec_digits, $varstr[$i]) > 0){
          $fsm_state = "dec";
        } else {
          $fsm_state = "fail";
        }
        break;
      case "zero":
      case "zero_sign":
        if ($varstr[$i] == "b"){
          $fsm_state = "bin_empty";
        } elseif ($varstr[$i] == "x"){
          $fsm_state = "hex_empty";
        } elseif (strpos($oct_digits, $varstr[$i]) > 0){
          $fsm_state = "oct";
        } else {
          $fsm_state = "fail";
        }
        break;
      default:
        echo "Err99: Internal failure (int validity check)";
        exit(99);
    }
  }
  if ($fsm_state == "fail"){
    return false;
  } else {
    return true;
  }
}

function print_arr_line($linearr){
  # Prints array of things (not other arrays) out on a line - debug function
  foreach($linearr as $word){
    echo "$word ";
  }
}

function xml_instr($linearr, $oporder){
  /*
  Instruction parser
  Checks number of args and arg types
  Outputs directly to STDOUT
  IN: linarr - array of strings, first instruction assumed to be valid opcode
    oporder - int, instruction counter
  */
  $cnt = count($linearr);
  GLOBAL $line;

  # opcode groups
  $opcodes_0 = array("CREATEFRAME", "PUSHFRAME", "POPFRAME",
    "RETURN", "BREAK");
  #$opcodes_un = array("DEFVAR", "CALL", "PUSHS", "POPS", "WRITE", "LABEL", "JUMP", "EXIT", "DPRINT");
  $opcodes_v = array("DEFVAR", "POPS");
  $opcodes_l = array("CALL", "LABEL", "JUMP");
  $opcodes_s = array("PUSHS", "WRITE", "EXIT", "DPRINT");
  #$opcodes_bin = array("MOVE", "INT2CHAR", "READ", "STRLEN", "TYPE");
  $opcodes_vs = array("MOVE", "INT2CHAR", "STRLEN", "TYPE", "NOT");
  $opcodes_vt = array("READ");
  #$opcodes_tern = array("ADD", "SUB", "MUL", "IDIV", "LT", "GT", "EQ", "AND", "OR", "NOT", "STR2INT", "CONCAT", "GETCHAR", "SETCHAR", "JUMPIFEQ", "JUMPIFNEQ");
  $opcodes_vss_arr = array("ADD", "SUB", "MUL", "IDIV");
  $opcodes_vss_cmp = array("LT", "GT", "EQ");
  $opcodes_vss_log = array("AND", "OR");
  $opcodes_vss_other = array("STRI2INT", "CONCAT", "GETCHAR", "SETCHAR");
  $opcodes_lss = array("JUMPIFEQ", "JUMPIFNEQ");

  $xml = " <instruction order=\"".$oporder."\" opcode=\"".$linearr[0]."\">\n";
  switch($cnt){
    case 1:
      if (in_array($linearr[0],$opcodes_0)){
        break;
      } else {
        # wrong number of args
        echo "Err23: Invalid number of arguments on line $line: ";
        print_arr_line($linearr);
        exit(23);
      }
    case 2:
      if (in_array($linearr[0], $opcodes_v)){
        if (is_it_($linearr[1], "var")){
          $xml .= xml_var($linearr[1], 1);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else if (in_array($linearr[0], $opcodes_l)){
        # not checking label names
        $xml .= xml_label($linearr[1], 1);
      } else if (in_array($linearr[0], $opcodes_s)){
        # only EXIT has arg restrictions
        if (!($linearr[0] == "EXIT") || (is_it_($linearr[1], "var")) || (is_it_($linearr[1], "int")) ){
          $xml .= xml_sym($linearr[1], 1);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else {
        # wrong number of args
        echo "Err23: Invalid number of arguments on line $line: ";
        print_arr_line($linearr);
        exit(23);
      }
      break;
    case 3:
      if (in_array($linearr[0], $opcodes_vs)){
        if (is_it_($linearr[1], "var")){
          if ($linearr[0] == "MOVE" ||
            ($linearr[0] == "INT2CHAR" && (is_it_($linearr[2], "int") || is_it_($linearr[2], "var")))||
            ($linearr[0] == "STRLEN" && (is_it_($linearr[2], "string") || is_it_($linearr[2], "var")))||
            $linearr[0] == "TYPE"||
            ($linearr[0] == "NOT" && (is_it_($linearr[2], "bool") || is_it_($linearr[2], "var")))
          ){
            $xml .= xml_var($linearr[1], 1);
            $xml .= xml_sym($linearr[2], 2);
          } else {
            # wrong arg type
            echo "Err23: Invalid argument type on line $line: ";
            print_arr_line($linearr);
            exit(23);
          }
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else if (in_array($linearr[0], $opcodes_vt)){
        if (is_it_($linearr[1], "var") && is_it_($linearr[2], "type")){
          $xml .= xml_var($linearr[1], 1);
          $xml .= xml_type($linearr[2], 2);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else {
        # wrong number of args
        echo "Err23: Invalid number of arguments on line $line: ";
        print_arr_line($linearr);
        exit(23);
      }
      break;
    case 4:
      if (in_array($linearr[0], $opcodes_vss_arr)){
        if (is_it_($linearr[1], "var") &&
          (is_it_($linearr[2], "int") || is_it_($linearr[2], "var")) &&
          (is_it_($linearr[3], "int") || is_it_($linearr[2], "var"))){
          $xml .= xml_var($linearr[1], 1);
          $xml .= xml_sym($linearr[2], 2);
          $xml .= xml_sym($linearr[3], 3);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else if (in_array($linearr[0], $opcodes_vss_cmp)){
        if (is_it_($linearr[1], "var") && !is_it_($linearr[2], "nil") && is_it_same($linearr[2], $linearr[3])){
          $xml .= xml_var($linearr[1], 1);
          $xml .= xml_sym($linearr[2], 2);
          $xml .= xml_sym($linearr[3], 3);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else if (in_array($linearr[0], $opcodes_vss_log)){
        if (is_it_($linearr[1], "var") &&
          (is_it_($linearr[2], "bool") || is_it_($linearr[2], "var")) &&
          (is_it_($linearr[3], "bool") || is_it_($linearr[2], "var"))){
          $xml .= xml_var($linearr[1], 1);
          $xml .= xml_sym($linearr[2], 2);
          $xml .= xml_sym($linearr[3], 3);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else if (in_array($linearr[0], $opcodes_vss_other)){
        switch($linearr[0]){
          case "STRI2INT":
          case "GETCHAR":
            if (is_it_($linearr[1], "var") &&
              (is_it_($linearr[2], "string") || is_it_($linearr[2], "var")) &&
              (is_it_($linearr[3], "int") || is_it_($linearr[2], "var"))){
              $xml .= xml_var($linearr[1], 1);
              $xml .= xml_sym($linearr[2], 2);
              $xml .= xml_sym($linearr[3], 3);
            } else {
              # wrong arg type
              echo "Err23: Invalid argument type on line $line: ";
              print_arr_line($linearr);
              exit(23);
            }
            break;
          case "CONCAT":
            if (is_it_($linearr[1], "var") &&
              (is_it_($linearr[2], "string") || is_it_($linearr[2], "var")) &&
              (is_it_($linearr[3], "string") || is_it_($linearr[2], "var"))){
              $xml .= xml_var($linearr[1], 1);
              $xml .= xml_sym($linearr[2], 2);
              $xml .= xml_sym($linearr[3], 3);
            } else {
              # wrong arg type
              echo "Err23: Invalid argument type on line $line: ";
              print_arr_line($linearr);
              exit(23);
            }
            break;
          case "SETCHAR":
            if (is_it_($linearr[1], "var") &&
              (is_it_($linearr[2], "int") || is_it_($linearr[2], "var")) &&
              (is_it_($linearr[3], "string") || is_it_($linearr[2], "var"))){
              $xml .= xml_var($linearr[1], 1);
              $xml .= xml_sym($linearr[2], 2);
              $xml .= xml_sym($linearr[3], 3);
            } else {
              # wrong arg type
              echo "Err23: Invalid argument type on line $line: ";
              print_arr_line($linearr);
              exit(23);
            }
            break;
          # no default
        }
      } else if (in_array($linearr[0], $opcodes_lss)){
        if (is_it_same($linearr[2], $linearr[3]) || is_it_($linearr[2], "nil") || is_it_($linearr[3], "nil") ||
          is_it_($linearr[2], "var") || is_it_($linearr[3], "var")){
          $xml .= xml_label($linearr[1], 1);
          $xml .= xml_sym($linearr[2], 2);
          $xml .= xml_sym($linearr[3], 3);
        } else {
          # wrong arg type
          echo "Err23: Invalid argument type on line $line: ";
          print_arr_line($linearr);
          exit(23);
        }
      } else {
        # wrong number of args
        echo "Err23: Invalid number of arguments on line $line: ";
        print_arr_line($linearr);
        exit(23);
      }
      break;
    default:
      # too many args
      echo "Err23: Invalid number of arguments on line $line: ";
      print_arr_line($linearr);
      exit(23);
  }
  $xml .= " </instruction>\n";
  fwrite(STDOUT, $xml);
}

function main($argv){
  $ctrl = parse_argv($argv);
  if ($ctrl["help"]){
    print_help($argv[0]);
    exit(0);
  }

  GLOBAL $line;

  # head check
  while(true){
    $line++;
    # skip empty and comment lines
    $currline = trim(fgets(STDIN, 1024));
    $currline = trim(preg_split("/[#]/", $currline)[0]);
    if (ord($currline) != 0){
      break;
    }
  }
  if ($currline != ".IPPcode22"){
    echo "Err21: Invalid header on line $line";
    exit(21);
  }

  fwrite(STDOUT, '<?xml version="1.0" encoding="UTF-8"?>'."\n");
  fwrite(STDOUT, '<program language="IPPcode22">'."\n");

  # opcode master list
  $opcodes = array("CREATEFRAME", "PUSHFRAME", "POPFRAME",
    "RETURN", "BREAK", "DEFVAR", "POPS", "CALL", "LABEL", "JUMP",
    "PUSHS", "WRITE", "EXIT", "DPRINT", "MOVE", "INT2CHAR", "STRLEN",
    "TYPE", "READ", "ADD", "SUB", "MUL", "IDIV", "LT", "GT", "EQ",
    "AND", "OR", "NOT", "STRI2INT", "CONCAT", "GETCHAR", "SETCHAR",
    "JUMPIFEQ", "JUMPIFNEQ");

  # main loop
  $oporder = 0;
  while (!feof(STDIN)){
    $line++;
    $oporder++;
    $currline = trim(fgets(STDIN, 1024));
    #echo "Read $currline on line $line\n";

    # purging comments
    $currline = trim(preg_split("/[#]/", $currline)[0]);
    #echo "Uncommented ", $currline, "\n";

    # whitespace split
    $currarr = preg_split("/[\s]+/", $currline);
    #print_r($currarr);
    #echo ord($currarr[0]), "\n";

    $currarr[0] = strtoupper($currarr[0]);
    #echo $currarr[0];
    if (ord($currarr[0]) == 0){
      # comment or empty line
      #echo "empty";
      $oporder--;
    } else if (in_array($currarr[0], $opcodes)){
      # parse line and output
      xml_instr($currarr, $oporder);
    } else {
      # invalid opcode
      echo "Err22: Invalid opcode on line $line: $currline";
      exit(22);
    }
  }
  fwrite(STDOUT, "</program>\n");
  exit(0);
}

main($argv);
 ?>
