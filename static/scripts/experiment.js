var my_node_id = null;

var p = 0.5;         
var s = null;         
var g = null;
var generalizedPositions = [];
var transmittedPositions = [];
var transmittedAnswers = {};
var task = null;
var toSolve = null;
var answers = [];
var activeIndex = 0;

var currentTimestep = 0;
var lifespanL = 5;  // established at front end for now 

var feedbackCorrectness = {};
var showingFeedback = false;




function arrowLabel(value) {
  switch (value) {
    case "UP": return "↑";
    case "DOWN": return "↓";
    case "LEFT": return "←";
    case "RIGHT": return "→";
    default: return "";
  }
}

function updateSubmitEnabled() {
  if (my_node_id !== null) {
    $("#submit").prop("disabled", false);
  } else {
    $("#submit").prop("disabled", true);
  }
  // check if all positions are filled
  var allFilled = true;
  for (var i = 0; i < toSolve; i++) {
    if (answers[i] === null) {
      allFilled = false;
      break;
    }
  }

  if (!allFilled) {
    $("#submit").prop("disabled", true);
  }
}

function setStatus(msg) {
  $("#status").text(msg);
}

function renderGrid() {
  renderParentGrid();
  //temporary
  console.log("renderGrid called. showingFeedback =", showingFeedback, "feedbackCorrectness =", feedbackCorrectness);
  var $grid = $("#grid");
  $grid.empty();
  $grid.css({
    display: "flex",
    flexDirection: "row", 
    gap: "8px"
  })

  for (var i = 0; i < toSolve; i++) {
    var $cell = $("<div></div>");
    $cell.addClass("gc-cell");
    $cell.attr("data-index", i);
    $cell.text(arrowLabel(answers[i]));

    var key = String(i);
    var borderStyle = "1px solid #999";
    var backgroundColor = "white";
    var textColor = "black";

    // generalized positions always blue
    if (generalizedPositions.includes(i)) {
    backgroundColor = "#d0ebff";
    }

    // transmitted hints: make text lighter before feedback
    if (!showingFeedback && transmittedAnswers[key] !== undefined) {
    textColor = "#555";
    }

    // feedback overrides background
    if (showingFeedback && feedbackCorrectness[key] !== undefined) {
    if (feedbackCorrectness[key]) {
    borderStyle = "3px solid green";
    backgroundColor = "#d4edda";
    } else {
    borderStyle = "3px solid red";
    backgroundColor = "#f8d7da";
    }
    } else if (!showingFeedback && i === activeIndex) {
    borderStyle = "3px solid #000";
    }


    $cell.css({
      width: "60px",
      height: "60px",
      border: borderStyle,
      backgroundColor: backgroundColor,
      color: showingFeedback && Object.prototype.hasOwnProperty.call(feedbackCorrectness, key)
        ? (feedbackCorrectness[key] === true ? "green" : "red")
        : textColor,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "30px",
      cursor: showingFeedback ? "default" : "pointer",
      userSelect: "none"
    });

    (function(index){
      $cell.on("click", function() {
        if (showingFeedback) {return;}
        activeIndex = index;
        renderGrid();
        updateSubmitEnabled();
      });
    })(i);

    $grid.append($cell);
  }
}

function renderParentGrid() {
  var $grid = $("#parent-grid");
  $grid.empty();
  $grid.css({
    display: "flex",
    flexDirection: "row", 
    gap: "8px"
  })
  
  for (var i = 0; i < toSolve; i++) {
  var $cell = $("<div></div>");
  $cell.addClass("gc-cell");
  
  var key = String(i);
  var parentValue = transmittedAnswers[key] !== undefined ? transmittedAnswers[key] : null;
  if (parentValue == null) {
    $cell.text("?");
  }
  else {
    $cell.text(arrowLabel(parentValue));
  }
  
  
  var backgroundColor = "white";
  var textColor = "#555"
  
  if (generalizedPositions.includes(i)) {
  backgroundColor = "#d0ebff";
  }

  if (parentValue == null) {
    textColor = "#999";
  }
  
  $cell.css({
  width: "60px",
  height: "60px",
  border: "1px solid #999",
  backgroundColor: backgroundColor,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "30px",
  color: textColor,
  userSelect: "none"
  });
  
  $grid.append($cell);
  }
  }

  
function handleKeydown(e) {
  if (showingFeedback) {
    return;
  }

  if (e.which === 13) {
    e.preventDefault();
    
    if (!$("#submit").prop("disabled")) {
    submitTimestep();
    }
    
    return;
    }

  // Backspace deletes the most recent filled answer
if (e.which === 8) {
  e.preventDefault();
  
  var lastFilled = -1;
  for (var i = toSolve - 1; i >= 0; i--) {
  if (answers[i] !== null) {
  lastFilled = i;
  break;
  }
  }
  
  if (lastFilled >= 0) {
  answers[lastFilled] = null;
  activeIndex = lastFilled;
  renderGrid();
  updateSubmitEnabled();
  }
  
  return;
  }

  var map = { 37: "LEFT", 38: "UP", 39: "RIGHT", 40: "DOWN" };
  var val = map[e.which || e.keyCode];
  if (!val) return;

  e.preventDefault();
  answers[activeIndex] = val;

  if (activeIndex < toSolve - 1) activeIndex += 1;

  renderGrid();
  updateSubmitEnabled();
}

function enableSubmitIfReady() {
  $("#submit").prop("disabled", my_node_id === null);
}


create_agent = function() {
  setStatus("Initializing participant...");
  $("#submit").prop("disabled", true);

  $(document).off("keydown.gc").on("keydown.gc", handleKeydown);
  $("#submit").off("click.gc").on("click.gc", submitTimestep); // ensures submit runs submitTimestep()

  $("#continue").off("click.gc").on("click.gc", function() { // after clicking continue
    console.log("continue clicked"); //temp
    feedbackCorrectness = {}; // clearing feedback
    showingFeedback = false; 
  
    $("#continue").hide();
    $("#submit").show();
    $("#submit").prop("disabled", false);
  
    if (currentTimestep < lifespanL) {
      initializeTimestep();
    } else {
      setStatus("Finished all timesteps.");
      dallinger.allowExit();
      dallinger.goToPage("questionnaire");
    }
  });

  dallinger.createAgent() // create backend node
    .done(function(resp) {
      my_node_id = resp.node.id;

      dallinger.getInfos(my_node_id, {
        info_type: "NodeAlleles" // get the node's alleles
      }).done(function(resp2) {
        var alleleInfo = resp2.infos[0];
        var alleles = JSON.parse(alleleInfo.contents);

        s = alleles.s;
        g = alleles.g;
        currentTimestep = 0;
        initializeTimestep();
      });
    })
    .fail(function(rejection) {
      if (rejection.status === 403) {
        dallinger.allowExit();
        dallinger.goToPage("questionnaire");
      } else {
        dallinger.error(rejection);
      }
    });
};

function initializeTimestep() {
  currentTimestep += 1;
   
  $("#submit").prop("disabled", true);
  
  dallinger.getInfos(my_node_id).done(function(resp) {
  var infos = resp.infos || [];
  
  var timestepInfos = infos.filter(function(info) { // not sure about the filter part here
  return info.type === "timestep_info"; // getting relevant info about how many to solve, generalized, etc.
  }); 
  
  if (timestepInfos.length === 0) {
  console.log("No timestep info found");
  setStatus("No timestep info found.");
  $("#submit").prop("disabled", true);
  return;
  }
  
  var timestepInfo = timestepInfos[timestepInfos.length - 1]; // don't know why
  
  var payload = JSON.parse(timestepInfo.contents);
  
  console.log("Loaded timestep payload:", payload);
  
  if (!payload.task || payload.toSolve === undefined) {
  console.log("Invalid timestep payload:", payload);
  setStatus("Invalid timestep payload.");
  $("#submit").prop("disabled", true);
  return;
  }
  
  task = payload.task;
  toSolve = payload.toSolve;
  generalizedPositions = payload.generalized_positions || [];
  transmittedPositions = payload.transmitted_positions || [];
  transmittedAnswers = payload.transmitted_answers || {};
  
  answers = Array(toSolve).fill(null); // make array that will be filled with answers later
  
  activeIndex = 0;
  showingFeedback = false;
  feedbackCorrectness = {};
  
  $("#continue").hide();
  $("#submit").show();
  $("#submit").prop("disabled", false); 
  
 $("#Main-header").html("Task " + task)
 $("#timestep").html("Timestep " + currentTimestep + "of " + lifespanL)
  
  renderGrid();
  updateSubmitEnabled(); // not sure why we're calling this
  }).fail(function(err) {
  console.log("Failed to load timestep info:", err);
  setStatus("Failed to load timestep.");
  $("#submit").prop("disabled", true);
  });
}


function submitTimestep() {
  for (var i = 0; i < toSolve; i++) {
    if (answers[i] === null) {
      setStatus("Please fill in all boxes before submitting.");
      return;
    }
  }
  
  if (my_node_id === null) return;

  var payload = {
    kind: "task_answer",
    timestep: currentTimestep,
    lifespanL: lifespanL,
    task: task,
    s: s,
    toSolve: toSolve,
    answers: answers,
    transmittedAnswers: transmittedAnswers,
    generalizedPositions: generalizedPositions
  };

  setStatus("Submitting...");
  $("#submit").prop("disabled", true);

  dallinger.createInfo(my_node_id, {
    contents: JSON.stringify(payload),
    info_type: "TaskAnswer"
  })
  .done(function() {
    console.log("TaskAnswer saved successfully");

    dallinger.getInfos(my_node_id).done(function(resp) {
      var infos = resp.infos || [];
      
      var feedbackInfos = infos.filter(function(info) {
      return info.type === "feedback_info";
      });
      
      if (feedbackInfos.length === 0) {
      console.log("No feedback found");
      $("#submit").prop("disabled", false);
      return;
      }
      
      var feedbackInfo = feedbackInfos[feedbackInfos.length - 1]; //idk why
      var feedback = JSON.parse(feedbackInfo.contents);
      
      feedbackCorrectness = feedback.feedback_correctness || {};
      generalizedPositions = feedback.generalized_positions || [];
      showingFeedback = true;
      
      setStatus("Feedback shown. Green = correct, red = incorrect.");
      $("#submit").hide();
      $("#continue").show();
      
      renderGrid();
      });
  })
  .fail(function(err) {
    console.log("SUBMIT FAILED:", err);
    setStatus("Submit failed. Check console.");
    $("#submit").prop("disabled", false);
  });
}

